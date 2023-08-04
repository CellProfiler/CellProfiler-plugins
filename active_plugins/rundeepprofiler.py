#################################
#
# Imports from useful Python libraries
#
#################################
import random
import os
import shutil
import subprocess
import csv
import numpy as np
import logging

from cellprofiler_core.module import Module
from cellprofiler_core.setting.subscriber import LabelSubscriber
from cellprofiler_core.setting.text import Text, Filename, Directory
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
    Measurement,
    Binary,
)
from cellprofiler_core.setting.subscriber import (
    ImageListSubscriber,
)
from cellprofiler_core.constants.measurement import COLTYPE_FLOAT, C_LOCATION

LOGGER = logging.getLogger(__name__)

C_MEASUREMENT = "DeepProfiler"

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
        
        self.save_features = Binary(
            "Write outputs to final objects table?",
            True,
            doc="""\
Select "*{YES}*" to save the features generated by DeepProfiler into your final output object table.

Note that if you select No, the outputs will be located in the output directory selected by you.""".format(
                **{"YES": "Yes"}
            ),
        )

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
        return [self.images_list, self.input_object_name, self.assay,
                self.metadata_plate, self.metadata_well, self.metadata_site,
                self.save_features, self.directory, self.app_directory, 
                self.model_directory, self.model_filename, 
                self.config_directory, self.config_filename]
    #
    # CellProfiler calls "run" on each image set in your pipeline.
    #
    def run(self, workspace):

        if self.show_window:
            workspace.display_data.col_labels = (
                "Object",
                "Feature",
                "Mean",
                "Median",
                "STD",
            )
            workspace.display_data.statistics = self.statistics = []
        #
        # Get directories
        # 
        try:
            self.out_directory = self.directory.get_absolute_path()
            model_dir = self.model_directory.get_absolute_path()
            config_dir = self.config_directory.get_absolute_path()
            deep_directory = self.app_directory.get_absolute_path()

            #
            # Create folders using deepprofiler setup
            #
            executable = os.path.join(f"{deep_directory}","deepprofiler")
            cmd_setup = f"python {executable} --root={self.out_directory} setup"
            result = subprocess.run(cmd_setup.split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) 
            if result.returncode!=0: 
                msg = f"The call to DeepProfiler ({cmd_setup}) returned an error; you should try to solve this outside of CellProfiler. DeepProfiler output was as follows: \n {result.stdout}" 
                raise RuntimeError(msg)

            # 
            # Copy model and config to the folders deepprofiler expects
            #
            local_output = os.path.join(f"{self.out_directory}","outputs",f"{self.assay.value}","checkpoint")
            os.makedirs(local_output, exist_ok=True)
            local_input = os.path.join(f"{self.out_directory}","inputs","config")
            os.makedirs(local_input, exist_ok=True)
            shutil.copy(os.path.join(f"{model_dir}",f"{self.model_filename.value}"), local_output)
            shutil.copy(os.path.join(f"{config_dir}",f"{self.config_filename.value}"), local_input)

            #
            # Locations file
            # creates a location file for each site with the nuclei_center
            #
            # Get the measurements object
            self.measurements = workspace.measurements
            # Get inputs
            x_obj = self.measurements.get_current_measurement(self.input_object_name.value, "Location_Center_X")
            y_obj = self.measurements.get_current_measurement(self.input_object_name.value, "Location_Center_Y")
            self.well = self.measurements.get_current_image_measurement(self.metadata_well.value)
            self.site = self.measurements.get_current_image_measurement(self.metadata_site.value)
            # Create plate directory and location file
            loc_dir = os.path.join(f"{self.out_directory}","inputs","locations",f"{self.metadata_plate.value}")
            loc_file = f"{self.well}-{self.site}-Nuclei.csv"
            os.makedirs(loc_dir, exist_ok=True)
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
            filename_list = [self.metadata_plate.value, self.well, self.site]
            for img in self.images_list.value:
                pathname = self.measurements.get_current_image_measurement(f"PathName_{img}")
                filename = self.measurements.get_current_image_measurement(f"FileName_{img}")
                filename_list.append(os.path.join(f"{pathname}",f"{filename}"))
            header_files.extend(self.images_list.value)
            index_dir = os.path.join(f"{self.out_directory}","inputs","metadata")
            os.makedirs(index_dir, exist_ok=True)
            index_file = f"index_{str(random.randint(100000, 999999))}.csv"
            indexpath = os.path.join(index_dir, index_file)
            with open(indexpath, 'w', newline='', encoding='utf-8') as fpointer:
                    writer = csv.writer(fpointer)
                    writer.writerow(header_files)
                    writer.writerow((filename_list))
  
            #
            # RUN!
            #
            cmd_run = f"python {executable} --root={self.out_directory} --config {self.config_filename.value} --metadata {index_file} --exp {self.assay.value} profile"
            result = subprocess.run(cmd_run.split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            if result.returncode!=0:
                msg = f"The call to DeepProfiler ({cmd_run}) returned an error; you should try to solve this outside of CellProfiler. DeepProfiler output was as follows: \n {result.stdout}"
                raise RuntimeError(msg)
        finally:
            #
            # Get the outputs to save and/or display on window
            #
            self.columns_names, self.features = self.get_measurements_deepprofiler()
            object_name = self.input_object_name.value
            for i in range(len(self.columns_names)):
                if self.show_window and len(self.features[i]) > 0:
                                self.statistics.append(
                                    (
                                        object_name,
                                        self.columns_names[i],
                                        np.round(np.mean(self.features[i]), 3),
                                        np.round(np.median(self.features[i]), 3),
                                        np.round(np.std(self.features[i]), 3),
                                    )
                                )
                self.measurements.add_measurement(
                    object_name,
                    self.columns_names[i],
                    self.features[i],
                )
            #
            # Delete files after run in inputs folder
            #
            want_delete = True
            input_dir = os.path.join(f"{self.out_directory}","inputs")
            if workspace.pipeline.test_mode:
                want_delete = False
            if want_delete and self.save_features.value:
                try:
                    for subdir, dirs, files in os.walk(input_dir):
                        for file in files:
                            os.remove(os.path.join(input_dir, file))
                    os.removedirs(input_dir)
                except:
                    LOGGER.error("Unable to delete temporary directory, files may be in use by another program.")
                    LOGGER.error("Temp folder is subfolder {input_dir} in your Default Output Folder.\nYou may need to remove it manually.")
            else:
                LOGGER.error(f"Did not remove temporary input folder at {input_dir}")

    def record_measurements(self, object_name, feature_name_list, results):
        for i in range(len(feature_name_list)):
            if self.show_window and len(results[i]) > 0:
                            self.statistics.append(
                                (
                                    object_name,
                                    feature_name_list[i],
                                    np.round(np.mean(results[i]), 3),
                                    np.round(np.median(results[i]), 3),
                                    np.round(np.std(results[i]), 3),
                                )
                            )
            self.measurements.add_measurement(
                object_name,
                feature_name_list[i],
                results[i],
            )
        return
    
    def get_measurements_deepprofiler(self):
        feat_dir = os.path.join(f"{self.out_directory}","outputs",f"{self.assay.value}","features", f"{self.metadata_plate.value}", f"{self.well}")
        feat_file = f"{self.site}.npz"
        features = os.path.join(f"{feat_dir}", f"{feat_file}")
        self.file = np.load(features, allow_pickle=True)
        columns_names = ["DeepProfiler_"+str(x+1) for x in range(0, len(self.file["features"][0]+1))]
        return columns_names, self.file["features"].transpose()
    
    def get_measurement_columns(self, pipeline):
        input_object_name = self.input_object_name.value
        columns = []
        # This shouldn't be hardcode for DeepProfiler only = 672 columns. Change that!
        for feature in range(0, 672): 
            columns.append(
                (
                    input_object_name,
                    "%s_%s" % (C_MEASUREMENT, feature+1),
                    COLTYPE_FLOAT,
                )
            )
        return columns
    
    def get_categories(self, pipeline, object_name):
        if object_name == self.input_object_name:
            return [C_MEASUREMENT]
        else:
            return []
    
    def get_measurements(self, pipeline, object_name, category):
        if category == C_MEASUREMENT and object_name == self.input_object_name:
            return self.get_measurement_columns(pipeline)
        return []

    def display(self, workspace, figure):
        figure.set_subplots((1, 1))
        figure.subplot_table(
            0,
            0,
            workspace.display_data.statistics,
            col_labels=workspace.display_data.col_labels,
            title="Per-object means. Get the per-object results on the output object's table",
        )
        