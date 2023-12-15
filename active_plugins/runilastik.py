#################################
#
# Imports from useful Python libraries
#
#################################

import os
import subprocess
import shutil
import uuid
import logging
import sys
import h5py 
import tempfile


#################################
#
# Imports from CellProfiler
#
##################################

from cellprofiler_core.image import Image
from cellprofiler_core.module import ImageProcessing
from cellprofiler_core.setting.choice import Choice
from cellprofiler_core.preferences import get_default_output_directory
from cellprofiler_core.setting.text import (
    Directory,
    Filename,
    Pathname,
)

ilastik_link = "https://doi.org/10.1038/s41592-019-0582-9"
LOGGER = logging.getLogger(__name__)


__doc__ = """\
Runilastik
=======

Use an ilastik pixel classifier to generate a probability image. Each
channel represents the probability of the pixels in the image belong to
a particular class. Use **ColorToGray** to separate channels for further
processing. For example, use **IdentifyPrimaryObjects** on a
(single-channel) probability map to generate a segmentation. The order
of the channels in **ColorToGray** is the same as the order of the
labels within the ilastik project.

Additionally, please ensure CellProfiler is configured to load images in
the same format as ilastik. For example, if your ilastik classifier is
trained on RGB images, use **NamesAndTypes** to load images as RGB by
selecting "*Color image*" from the *Select the image type* dropdown. If
your classifier expects grayscale images, use **NamesAndTypes** to load
images as "*Grayscale image*".

Add more documentation.
"""

ILASTIK_DOCKER = "biocontainers/ilastik:1.4.0_cv2"

class Runilastik(ImageProcessing):
    module_name = "Runilastik"

    variable_revision_number = 1  

    doi = {
        "Please cite the following when using Runilastik:": "https://doi.org/10.1038/s41592-019-0582-9",
    }

    def create_settings(self):
        super(Runilastik, self).create_settings()

        self.docker_or_local = Choice(
            text="Run ilastik in docker or local environment",
            choices=["Docker", "Local"],
            value="Docker",
            doc="""\
If Docker is selected, ensure that Docker Desktop is open and running on your
computer. On first run of the Runilastik plugin, the Docker container will be
downloaded. However, this slow downloading process will only have to happen
once.

If Local is selected, the local install of ilastik will be used.
""",
        )

        self.executable = Pathname(
            "Executable",
            doc="ilastik command line executable name, or location if it is not on your path."
        )

        self.project_file = Pathname(
            "Project file",
            doc="Path to the project file (\*.ilp)."
        )

        self.project_type = Choice(
            "Select the project type",
            [
                "Pixel Classification",
                "Autocontext (2-stage)"
            ],
            "Pixel Classification",
            doc="""\
Select the project type which matches the project file specified by
*Project file*. CellProfiler supports two types of ilastik projects:

-  *Pixel Classification*: Classify the pixels of an image given user
   annotations. `Read more`_.

-  *Autocontext (2-stage)*: Perform pixel classification in multiple
   stages, sharing predictions between stages to improve results. `Read
   more <http://ilastik.org/documentation/autocontext/autocontext>`__.

.. _Read more: http://ilastik.org/documentation/pixelclassification/pixelclassification
"""
        )

    def settings(self):
        return [
            self.x_name,
            self.y_name,
            self.docker_or_local,
            self.executable,
            self.project_file,
            self.project_type,
        ]
    def visible_settings(self):
        vis_settings = [self.docker_or_local]

        if self.docker_or_local.value == "Local":
            vis_settings += [self.executable]

        vis_settings += [self.x_name, self.y_name, self.project_file, self.project_type]
        
        return vis_settings
    
    def run(self, workspace):
        image = workspace.image_set.get_image(self.x_name.value)

        x_data = image.pixel_data
        x_data = x_data*image.scale    #rescale 

        # preparing the data
        
        # Directory that will be used to pass images to the docker container
        # Create a UUID for this run
        unique_name = str(uuid.uuid4())
        
        temp_dir = os.path.join(get_default_output_directory(), ".cellprofiler_temp", unique_name)

        os.makedirs(temp_dir, exist_ok=True)

        fin = tempfile.NamedTemporaryFile(suffix=".h5", dir=temp_dir, delete=False)

        fout = tempfile.NamedTemporaryFile(suffix=".h5", dir=temp_dir, delete=False)

        
        with h5py.File(fin.name, "w") as f:
            shape = x_data.shape
            # Previously, code lived here that added an explicit channel dimension in grayscale
            # It now seems to harm rather than help, but may need to be resurrected in some corner case not thoroughly tested
            
            f.create_dataset("data", shape, data=x_data)

        fin.close()

        fout.close()

        if self.docker_or_local.value == "Docker":
            # Define how to call docker
            docker_path = "docker" if sys.platform.lower().startswith("win") else "/usr/local/bin/docker"
                       
            model_file = self.project_file.value
            model_directory = os.path.dirname(os.path.abspath(model_file)) 

            fout_name = f"/data/{os.path.basename(fout.name)}"
            fin_name = f"/data/{os.path.basename(fin.name)}"

            cmd = [f"{docker_path}", "run", "--rm", "-v", f"{temp_dir}:/data",
            "-v", f"{model_directory}:/model",
            f"{ILASTIK_DOCKER}", "/opt/ilastik-1.4.0-Linux/run_ilastik.sh", "--headless",
            "--project", f"/model/{os.path.basename(model_file)}"
            ]

        if self.docker_or_local.value == "Local":

            if self.executable.value[-4:] == ".app":
                executable = os.path.join(self.executable.value, "Contents/MacOS/ilastik")
            else:
                executable = self.executable.value

            fout_name = fout.name
            fin_name = fin.name

            cmd = [
            executable,
            "--headless",
            "--project", self.project_file.value]

        cmd += ["--output_format", "hdf5"]
        

        if self.project_type.value in ["Pixel Classification"]:
            cmd += ["--export_source", "Probabilities"]
        elif self.project_type.value in ["Autocontext (2-stage)"]:
            cmd += ["--export_source", "probabilities stage 2"]
            #cmd += ["--export_source", "probabilities all stages"]

        cmd += ["--output_filename_format", fout_name, fin_name]

        try:
            subprocess.check_call(cmd)


            with h5py.File(fout.name, "r") as f:
                y_data = f["exported_data"][()]

            y = Image(y_data)

            workspace.image_set.add(self.y_name.value, y)

            if self.show_window:
                workspace.display_data.x_data = x_data

                workspace.display_data.y_data = y_data

                workspace.display_data.dimensions = image.dimensions
        except subprocess.CalledProcessError as cpe:
            LOGGER.error("Command {} exited with status {}".format(cpe.output, cpe.returncode), cpe)

            raise cpe
        except IOError as ioe:
            raise ioe
        finally:
            os.unlink(fin.name)

            os.unlink(fout.name)

            # Delete the temporary files
            try:
                shutil.rmtree(temp_dir)
            except:
                LOGGER.error("Unable to delete temporary directory, files may be in use by another program.")
                LOGGER.error("Temp folder is subfolder {tempdir} in your Default Output Folder.\nYou may need to remove it manually.")

            
