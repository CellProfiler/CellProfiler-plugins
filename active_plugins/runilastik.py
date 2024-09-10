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
from cellprofiler_core.setting import ValidationError
from cellprofiler_core.setting.text import (
    Directory,
    Filename,
    Pathname,
    Text,
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

Runilastik module will not run analysis mode on local installation of ilastik on a Windows system. Please use Docker instead. 

A note to the mac users - this module takes a longer time to run using the Docker. 

Links to the Docker containers,
 biocontainers/ilastik:1.4.0_cv2 - https://hub.docker.com/layers/biocontainers/ilastik/1.4.0_cv2/images/sha256-0ccbca62d9efc63918d9de3b9b2bb5b1265a084f8b6410fd8c34e62869549791?context=explore
 ilastik/ilastik-from-binary:1.4.0b13 - https://hub.docker.com/layers/ilastik/ilastik-from-binary/1.4.0b13/images/sha256-e3a4044a5ac6f2086f4bf006c8a95e2bd6a6fbfb68831bb4ba47baf2fafba988?context=explore
"""

#ILASTIK_DOCKER is a dictionary where the keys are the names of the different docker containers and the values are the commands that are needed to run the respective docker container. 
ILASTIK_DOCKER = {"biocontainers/ilastik:1.4.0_cv2":'/opt/ilastik-1.4.0-Linux/run_ilastik.sh','ilastik/ilastik-from-binary:1.4.0b13':'./run_ilastik.sh', "select your own":''}
#Docker container that did not work - {'ilastik/ilastik-from-source:0.0.1a1':'. ~/.bashrc && python ilastik.py'}


class Runilastik(ImageProcessing):
    module_name = "Runilastik"

    variable_revision_number = 1  # the number of variations made to this module 

    doi = {
        "Please cite the following when using Runilastik:": "https://doi.org/10.1038/s41592-019-0582-9", # doi ias added such that it is easier for citations
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

                       
        self.docker_choice = Choice(
            text="Choose the docker",
            choices = list(ILASTIK_DOCKER.keys()),
            doc="""
Choose the docker that you would like to use for running ilastik
"""
        )

        self.custom_docker_name = Text(
            "Enter the docker name ",
            value="",
            doc="""
Please give your docker name
"""
        )

        self.docker_executable = Text(
            "Enter the executable command to run the docker",
            value="",
            doc="""
Please provide the executable command that is needed to run the docker command. You can find this in the github page of the docker.
"""
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
    # A function to define what settings should be displayed if an user chooses specific setting 
    def visible_settings(self): 
        
        vis_settings = [self.docker_or_local]
        if self.docker_or_local.value == "Docker":
            vis_settings += [self.docker_choice]

            if self.docker_choice == "select your own":
                vis_settings += [self.custom_docker_name, self.docker_executable]
        else:
            vis_settings += [self.executable]

        vis_settings += [self.x_name, self.y_name, self.project_file, self.project_type]
        
        return vis_settings
    
    # Give a warning if the user chooses "analysis mode"
    def validate_module_warnings(self, docker_or_local):
        """Warn user re: Analysis mode"""
        if self.docker_or_local.value == "Docker":
            if not sys.platform.lower().startswith("win"):
                raise ValidationError(
                    "Analysis mode will take a long time to run using Docker",
                    self.docker_or_local,
                )
        else: 
            if self.executable.value[-4:] == ".exe":
                raise ValidationError(
                    "Sorry, analysis will not run on Windows with the local installation of the ilastik. Please try Docker instead.",
                    self.docker_or_local,
                )

    def run(self, workspace):
        image = workspace.image_set.get_image(self.x_name.value)

        x_data = image.pixel_data
        x_data = x_data*image.scale    #rescale 

        # preparing the data
        # Create a UUID for this run
        unique_name = str(uuid.uuid4())
        
        # Directory that will be used to pass images to the docker container
        temp_dir = os.path.join(get_default_output_directory(), ".cellprofiler_temp", unique_name)

        os.makedirs(temp_dir, exist_ok=True)

        #The input image files are converted into h5 format and saved in the temporary directory 
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
            # The project file is stored in a directory which can be pointed to the docker            
            model_file = self.project_file.value
            model_directory = os.path.dirname(os.path.abspath(model_file)) 

            fout_name = f"/data/{os.path.basename(fout.name)}"
            fin_name = f"/data/{os.path.basename(fin.name)}"

                        
            if self.docker_choice.value == "select your own":
                ILASTIK_DOCKER_choice = self.custom_docker_name.value 
                ILASTIK_command = self.docker_executable.value

            else: 
                ILASTIK_DOCKER_choice = self.docker_choice.value
                ILASTIK_command = ILASTIK_DOCKER[ILASTIK_DOCKER_choice]
            
            cmd = [f"{docker_path}", "run", "--rm", "-v", f"{temp_dir}:/data",
            "-v", f"{model_directory}:/model",
            f"{ILASTIK_DOCKER_choice}", f"{ILASTIK_command}", "--headless",
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

            
