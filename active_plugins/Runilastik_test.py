#################################
#
# Imports from useful Python libraries
#
#################################

import numpy
import os
import skimage
import subprocess
import uuid
import shutil
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
from cellprofiler_core.module import Module
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

class Runilastik(cellprofiler_core.module.ImageProcessing):
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

        if self.docker_or_python.value == "Local":
            vis_settings += [self.executable]

        vis_settings += [self.x_name, self.y_name, self.project_file, self.project_type]
        
        return vis_settings
    
    def run(self, workspace):
        image = workspace.image_set.get_image(self.x_name.value)

        x_data = image.pixel_data
        x_data = x_data*image.scale

        fin = tempfile.NamedTemporaryFile(suffix=".h5", delete=False)

        fout = tempfile.NamedTemporaryFile(suffix=".h5", delete=False)

        if self.executable.value[-4:] == ".app":
            executable = os.path.join(self.executable.value, "Contents/MacOS/ilastik")
        else:
            executable = self.executable.value

        if self.docker_or_local.value == "Docker":
            # Define how to call docker
            docker_path = "docker" if sys.platform.lower().startswith("win") else "/usr/local/bin/docker"
            # Create a UUID for this run
            unique_name = str(uuid.uuid4())
            # Directory that will be used to pass images to the docker container
            temp_dir = os.path.join(get_default_output_directory(), ".cellprofiler_temp", unique_name)
            temp_img_dir = os.path.join(temp_dir, "img")
            
            os.makedirs(temp_dir, exist_ok=True)
            os.makedirs(temp_img_dir, exist_ok=True)

            temp_img_path = os.path.join(temp_img_dir, unique_name+".tiff")
            
            model_file = self.project_file.value
            model_directory = self.project_file.get_absolute_path()
            model_path = os.path.join(model_directory, model_file)
            temp_model_dir = os.path.join(temp_dir, "model")

            os.makedirs(temp_model_dir, exist_ok=True)
            # Copy the model
            shutil.copy(model_path, os.path.join(temp_model_dir, model_file))

            # Save the image to the Docker mounted directory
            skimage.io.imsave(temp_img_path, x_data)

            cmd = f"""
            {docker_path} run --rm -v {ILASTIK_DOCKER} /opt/ilastik-1.4.0-Linux/run_ilastik.sh {temp_dir}:/data
            {'--project'+temp_model_dir+model_file} # {temp_model_dir}
            {"--headless"}
            {"--output_format", "hdf5"}
            """

        if self.docker_or_local.value == "Local":

            cmd = [
            self.executable.value,
            "--headless",
            "--project", self.project_file.value,
            "--output_format", "hdf5"
        ]

        if self.project_type.value in ["Pixel Classification"]:
            cmd += ["--export_source", "Probabilities"]
        elif self.project_type.value in ["Autocontext (2-stage)"]:
            x_data = skimage.img_as_ubyte(x_data)  # ilastik requires UINT8. Might be relaxed in future.

            cmd += ["--export_source", "probabilities stage 2"]
            #cmd += ["--export_source", "probabilities all stages"]

        cmd += [
            "--output_filename_format", fout.name,
            fin.name
        ]

        try:
            with h5py.File(fin.name, "w") as f:
                shape = x_data.shape

                if x_data.ndim == 2:
                  # ilastik appears to add a channel dimension
                  # even if the image is grayscale
                  shape += (1,)
                
                f.create_dataset("data", shape, data=x_data)

            fin.close()

            fout.close()

            subprocess.check_call(cmd)

            with h5py.File(fout.name, "r") as f:
                y_data = f["exported_data"].value

            y = cellprofiler_core.image.Image(y_data)

            workspace.image_set.add(self.y_name.value, y)

            if self.show_window:
                workspace.display_data.x_data = x_data

                workspace.display_data.y_data = y_data

                workspace.display_data.dimensions = image.dimensions
        except subprocess.CalledProcessError as cpe:
            logger.error("Command {} exited with status {}".format(cpe.output, cpe.returncode), cpe)

            raise cpe
        except IOError as ioe:
            raise ioe
        finally:
            os.unlink(fin.name)

            os.unlink(fout.name)
            
