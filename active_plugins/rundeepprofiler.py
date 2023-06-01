#################################
#
# Imports from useful Python libraries
#
#################################

import centrosome.cpmorphology
import centrosome.zernike
import numpy
import scipy.ndimage
import numpy

from cellprofiler_core.setting.text import LabelName
from cellprofiler_core.setting.text import Text, Filename, Directory
from cellprofiler_core.setting.choice import Choice
from cellprofiler.modules import _help
from cellprofiler_core.preferences import ABSOLUTE_FOLDER_NAME
from cellprofiler_core.preferences import DEFAULT_INPUT_FOLDER_NAME
from cellprofiler_core.preferences import DEFAULT_INPUT_SUBFOLDER_NAME
from cellprofiler_core.preferences import DEFAULT_OUTPUT_FOLDER_NAME
from cellprofiler_core.preferences import DEFAULT_OUTPUT_SUBFOLDER_NAME
from cellprofiler_core.constants.module import (
    IO_FOLDER_CHOICE_HELP_TEXT,
    IO_WITH_METADATA_HELP_TEXT,
)
from cellprofiler_core.setting import (
    Divider,
    Binary,
    SettingsGroup,
    Measurement,
    ValidationError,
)
from cellprofiler_core.setting.subscriber import (
    ImageListSubscriber,
    LabelListSubscriber,
)
from cellprofiler_core.preferences import get_default_output_directory, get_headless
from cellprofiler_core.utilities.measurement import find_metadata_tokens
from cellprofiler_core.modules.metadata import Metadata
import cellprofiler_core.constants.measurement
from cellprofiler_core.pipeline._pipeline import Pipeline

import random
import os
import shutil
import subprocess
import csv

S_RULES = "Metadata"
IM_MEASUREMENT = "Measurement"
#################################
#
# Imports from CellProfiler
#
##################################

dp_doi = "https://doi.org/10.1101/2022.08.12.503783"
__doc__ = """\
RunDeepProfiler
===================

**RunDeepProfiler** - uses a pre trained CNN model on Cell Painting data to extract features from crops of single-cells using DeepProfiler software subprocess. 

This module will take a configuration file provided by the user to run DeepProfiler in the background. 
It will run only after the user install DeepProfiler in their machine and provide the path.

It depends on having an object previously identified by other modules such as IdentifyPrimaryObjects or RunCellpose to provide as Object_Location_Centers.


|

============ ============ ===============
Supports 2D? Supports 3D? Respects masks?
============ ============ ===============
YES          NO           NO
============ ============ ===============

See also
^^^^^^^^

What do I need as input?
^^^^^^^^^^^^^^^^^^^^^^^^

-  Objects: provide which object will be used as a center.
-  ExperimentName: enter a name for this experiment.
-  Define output directory: where to save the output features.
-  Define DeepProfiler directory: where DeepProfiler is located in your computer.
-  Path to the model: where the model/weight is located.
-  Define metadata Plate, Well, and Site: what are the metadata information (from load_csv or Metadata input module) that has those metadata 3 informations.  

What do I get as output?
^^^^^^^^^^^^^^^^^^^^^^^^

About 600 features will be saved inside the output > experiment_name > features > metadata_plate > Well > Site.csv 

For more on how to process those features, check pycytominer functionalities.

Measurements made by this module
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Describe the measurements made by this module. Typically, measurements
are described in the following format:

**DP**:

-  *EfficientNet_*: the outputs are one file for each site analyzed containing the single-cell features. 

Technical notes
^^^^^^^^^^^^^^^

DeepProfiler requires tensorflow-2.5.3 to run.

References
^^^^^^^^^^

DeepProfiler

-  Learning representations for image-based profiling of perturbations Nikita Moshkov, Michael Bornholdt, Santiago Benoit, Matthew Smith, Claire McQuin, 
    Allen Goodman, Rebecca A. Senft, Yu Han, Mehrtash Babadi, Peter Horvath, Beth A. Cimini, Anne E. Carpenter, Shantanu Singh, Juan C. Caicedo. bioRxiv 2022.08.12.503783
   {dp_doi}
-  DeepProfiler GitHub repository: https://github.com/cytomining/DeepProfiler
-  DeepProfiler handbook: https://cytomining.github.io/DeepProfiler-handbook/
"""

#
# Constants
#
# It's good programming practice to replace things like strings with
# constants if they will appear more than once in your program. That way,
# if someone wants to change the text, that text will change everywhere.
# Also, you can't misspell it by accident.
#
from cellprofiler_core.constants.measurement import COLTYPE_FLOAT
from cellprofiler_core.module import Module
from cellprofiler_core.setting.subscriber import ImageSubscriber, LabelSubscriber
from cellprofiler_core.setting.text import Integer

"""This is the measurement template category"""
C_MEASUREMENT_TEMPLATE = "MT"


class RunDeepProfiler(Module):
    module_name = "RunDeepProfiler"
    category = "Measurement"
    variable_revision_number = 1
    doi = {"Please cite DeepProfiler:": 'https://doi.org/10.1101/2022.08.12.503783'}

    def create_settings(self):
        self.images_list = ImageListSubscriber(
            "Select images to measure",
            [],
            doc="""Select the grayscale images whose intensity you want to measure.""",
        )

        self.input_object_name = LabelSubscriber(
            text="Provide nuclei object name",
            doc="Choose the name of the nuclei object to be used as a center.",
        )

        self.assay = Text(
            "Name this experiment.",
            "FeaturesDeepProfiler",
            doc="""\
Enter a name for your experiment. This will be used to create a folder inside the output folder""",
        )

        self.metadata_plate = Measurement(
                "Select the Metadata_Plate",
                lambda: "Image",
                "",
                doc="""\
Select a measurement made on the image. The value of the
measurement is used for the operand for all of the pixels of the
other operand's image.""",
            )
        
        self.metadata_well = Measurement(
                "Select the Metadata_Well",
                lambda: "Image",
                "",
                doc="""\
Select a measurement made on the image. The value of the
measurement is used for the operand for all of the pixels of the
other operand's image.""",
            )
        
        self.metadata_site = Measurement(
                "Select the Metadata_Site",
                lambda: "Image",
                "",
                doc="""\
Select a measurement made on the image. The value of the
measurement is used for the operand for all of the pixels of the
other operand's image.""",
            )

        self.directory = Directory(
            "Output folder",
            dir_choices=[
                ABSOLUTE_FOLDER_NAME,
                DEFAULT_OUTPUT_FOLDER_NAME,
                DEFAULT_OUTPUT_SUBFOLDER_NAME,
                DEFAULT_INPUT_FOLDER_NAME,
                DEFAULT_INPUT_SUBFOLDER_NAME,
            ],
            doc="""\
This setting lets you choose the folder for the output files. {folder_choice}

{metadata_help}
""".format(
                folder_choice=IO_FOLDER_CHOICE_HELP_TEXT,
                metadata_help=IO_WITH_METADATA_HELP_TEXT,
            ),
        )
        self.directory.dir_choice = DEFAULT_OUTPUT_FOLDER_NAME

        self.model_directory = Directory(
            "Model directory", allow_metadata=False, doc="""\
 Where the model is located.

{IO_FOLDER_CHOICE_HELP_TEXT}
""".format(**{
                "IO_FOLDER_CHOICE_HELP_TEXT": _help.IO_FOLDER_CHOICE_HELP_TEXT
            }))

        def set_directory_fn_executable(path):
            dir_choice, custom_path = self.model_directory.get_parts_from_path(path)
            self.model_directory.join_parts(dir_choice, custom_path)

        self.model_filename = Filename(
            "Model file", "Cell_Painting_CNN_v1.hdf5", doc="Select your DeepProfiler model. ",
            get_directory_fn=self.model_directory.get_absolute_path,
            set_directory_fn=set_directory_fn_executable,
            browse_msg="Choose executable file"
        )

        self.config_directory = Directory(
            "Configuration directory", allow_metadata=False, doc="""\
Select the folder containing the DeepProfiler configuration file.

{IO_FOLDER_CHOICE_HELP_TEXT}
""".format(**{
                "IO_FOLDER_CHOICE_HELP_TEXT": _help.IO_FOLDER_CHOICE_HELP_TEXT
            }))

        def set_directory_config_executable(path):
            dir_choice, custom_path = self.config_directory.get_parts_from_path(path)
            self.config_directory.join_parts(dir_choice, custom_path)

        self.config_filename = Filename(
            "Configuration file", "profiling.json", doc="Select your configuration file.",
            get_directory_fn=self.config_directory.get_absolute_path,
            set_directory_fn=set_directory_config_executable,
            browse_msg="Choose executable file"
        )
        
        self.app_directory = Directory(
            "DeepProfiler directory", doc="""\
Select the folder containing the DeepProfiler repository that you cloned to your computer.

{fcht}
""".format(
                fcht=IO_FOLDER_CHOICE_HELP_TEXT
            ),
        )


    def settings(self):
        return [self.images_list, self.input_object_name, self.assay, self.directory, self.app_directory, 
                self.model_directory, self.model_filename,
                self.metadata_plate, self.metadata_well, self.metadata_site,
                self.config_directory, self.config_filename]

    #
    # CellProfiler calls "run" on each image set in your pipeline.
    #
    def run(self, workspace):

        #
        # Get directories
        #         
        out_directory = self.directory.value.split("|")[1]
        model_dir = self.model_directory.value.split("|")[1]
        config_dir = self.config_directory.value.split("|")[1]
        deep_directory = self.app_directory.value.split("|")[1]

        #
        # Create folders using deepprofiler setup
        #
        executable = f"{deep_directory}\deepprofiler"
        cmd_setup = f"python {executable} --root={out_directory} setup"
        subprocess.run(cmd_setup, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

        # 
        # Copy model and config to the folders deepprofiler expects
        #
        os.makedirs(f"{out_directory}\outputs\{self.assay.value}\checkpoint", exist_ok=True)
        shutil.copy(f"{model_dir}\{self.model_filename.value}", f"{out_directory}\outputs\{self.assay.value}\checkpoint")
        shutil.copy(f"{config_dir}\{self.config_filename.value}", f"{out_directory}\inputs\config")

        #
        # Locations file
        # creates a location file for each site with the nuclei_center
        #
        # Get the measurements object
        measurements = workspace.measurements
        # Get inputs
        x_obj = measurements.get_current_measurement(self.input_object_name.value, "Location_Center_X")
        y_obj = measurements.get_current_measurement(self.input_object_name.value, "Location_Center_Y")
        plate = measurements.get_current_image_measurement(self.metadata_plate.value)
        well = measurements.get_current_image_measurement(self.metadata_well.value)
        site = measurements.get_current_image_measurement(self.metadata_site.value)
        print(plate, well, site)
        # Create plate directory and location file
        loc_dir = f"{out_directory}\inputs\locations\{self.metadata_plate.value}"
        loc_file = f"{well}-{site}-Nuclei.csv"
        os.makedirs(f"{out_directory}\inputs\locations\{self.metadata_plate.value}", exist_ok=True)
        # Create the actual file
        header = 'Nuclei_Location_Center_X', 'Nuclei_Location_Center_Y'
        csvpath = os.path.join(loc_dir, loc_file)
        with open(csvpath, 'w', newline='', encoding='utf-8') as fpointer:
                writer = csv.writer(fpointer)
                writer.writerow(header)
                for i in range(len(x_obj)):
                    writer.writerow((x_obj[i], y_obj[i]))
        #
        # Create the index/metadata file
        #
        header_files = ["Metadata_Plate", "Metadata_Well", "Metadata_Site"]
        filename_list = [self.metadata_plate.value, well, site]
        for img in self.images_list.value:
            pathname = measurements.get_current_image_measurement(f"PathName_{img}")
            filename = measurements.get_current_image_measurement(f"FileName_{img}")
            filename_list.append(f"{pathname}\{filename}")
        header_files.extend(self.images_list.value)
        print(filename_list)
        print(header_files)
        index_dir = f"{out_directory}\inputs\metadata"
        index_file = f"index_{str(random.randint(100000, 999999))}.csv"
        indexpath = os.path.join(index_dir, index_file)
        with open(indexpath, 'w', newline='', encoding='utf-8') as fpointer:
                writer = csv.writer(fpointer)
                writer.writerow(header_files)
                writer.writerow((filename_list))
              
        #
        # RUN!
        #
        cmd_run = f"python {executable} --root={out_directory} --config {self.config_filename.value} --metadata {index_file} --exp {self.assay.value} profile"
        subprocess.run(cmd_run, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

        if self.show_window:
            image_set_number = workspace.measurements.image_set_number
            header = ["Image", "Objects", "Output Folder"]
            columns = []
            for object_name in workspace.measurements.get_object_names():
                columns.append((image_set_number, object_name, out_directory))
            workspace.display_data.header = header
            workspace.display_data.columns = columns

    def display(self, workspace, figure):
        figure.set_subplots((1, 1))
        if workspace.display_data.columns is None:
            figure.subplot_table(0, 0, [["Data written to spreadsheet"]])
        elif workspace.pipeline.test_mode:
            figure.subplot_table(
                0, 0, [["Data not written to spreadsheets in test mode"]]
            )
        else:
            figure.subplot_table(
                0,
                0,
                workspace.display_data.columns,
                col_labels=workspace.display_data.header,
            )