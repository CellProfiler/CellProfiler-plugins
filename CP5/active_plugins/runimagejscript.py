#################################
#
# Imports from useful Python libraries
#
#################################

from os import path
from wx import Gauge
from wx import Window
from collections.abc import Iterable
from threading import Thread
from sys import platform
import time
import skimage.io
import cpij.bridge as ijbridge, cpij.server as ijserver

#################################
#
# Imports from CellProfiler
#
##################################

from cellprofiler_core.image import Image
from cellprofiler_core.module import Module
from cellprofiler_core.preferences import ABSOLUTE_FOLDER_NAME
from cellprofiler_core.setting.choice import Choice
from cellprofiler_core.setting.text import Filename, Text, Directory
from cellprofiler_core.constants.module import (
    IO_FOLDER_CHOICE_HELP_TEXT,
)
from cellprofiler_core.setting import ValidationError
from cellprofiler_core.setting import Binary
from cellprofiler_core.setting.do_something import DoSomething, RemoveSettingButton
from cellprofiler_core.setting._settings_group import SettingsGroup
from cellprofiler_core.setting import Divider, HiddenCount
from cellprofiler_core.setting.subscriber import ImageSubscriber

from wx import Gauge
from wx import Window
from collections.abc import Iterable
from threading import Thread
from sys import platform
import time
import skimage.io
import cpij.bridge as ijbridge, cpij.server as ijserver

imagej_link = "https://doi.org/10.1038/nmeth.2089"
imagej2_link = "https://doi.org/10.1186/s12859-017-1934-z"
pyimagej_link = "https://doi.org/10.1038/s41592-022-01655-4"

__doc__ = """\
RunImageJScript
=================

The **RunImageJScript** module allows you to run any supported ImageJ script as part
of your workflow.

First, select a script file. Then click the \"Get parameters from script\" button to detect required inputs for your
script. Each input will have its own setting created, allowing you to pass data from CellProfiler to ImageJ.

After filling in any required inputs you can run the script normally.

Optionally, you can select a local existing ImageJ installation to be used to run your script, or specify an initialization
string (per https://github.com/imagej/pyimagej/blob/master/doc/Initialization.md). If no input is provided, or the 
input is invalid, the latest version will be downloaded if necessary and used.

Notes
^^^^^^^

1. Only numeric, text and image input types are currently supported.
2. Outputs must be explicitly declared in the script via @OUTPUT
3. Only outputs of type net.imagej.Dataset or net.imagej.ImgPlus are currently supported

See also
^^^^^^^^

ImageJ Scripting: https://imagej.net/Scripting 
Schneider, C. A., Rasband, W. S., & Eliceiri, K. W. (2012). NIH Image to ImageJ: 25 years of image analysis. Nature Methods, 9(7), 671–675. {imagej_link}
Rueden, C. T., Schindelin, J., Hiner, M. C., DeZonia, B. E., Walter, A. E., Arena, E. T., & Eliceiri, K. W. (2017). ImageJ2: ImageJ for the next generation of scientific image data. BMC Bioinformatics, 18(1). {imagej2_link}
Rueden, C.T., Hiner, M.C., Evans, E.L. Pinkart, M.A., Lucas, A.M., Carpenter, A.E., Cimini, B.A., & Eliceiri, K. W. (2022). PyImageJ: A library for integrating ImageJ and Python. Nat Methods 19, 1326–1327 . {pyimagej_link}

 
"""

global stop_progress_thread
stop_progress_thread = False  # Used to control the display of progress graphics


class PyimagejError(EnvironmentError):
    """
    An exception indicating that something went wrong in PyimageJ
    """

    def __init__(self, message):
        super(EnvironmentError, self).__init__(message)
        self.message = message


def add_param_info_settings(group, param_name, param_type, param_class):
    """
    Each extracted name, type and input/output class is saved into a (hidden) setting. This is useful information to
    have when saving and loading pipelines back into CellProfiler.

    Parameters
    ----------
    group : SettingsGroup, required
        The SettingsGroup for this parameter, to hold the hidden info settings
    param_name : str, required
        The name of the parameter
    param_type : str, required
        The Java class name describing the parameter type
    param_class: str, required
        One of {input_class} or {output_class}, based on the parameter use
    """
    group.append("name", Text("Parameter name", param_name))
    group.append(
        "type",
        Text("Parameter type", param_type),
    )
    group.append(
        "io_class",
        Text("Parameter classification", param_class),
    )


class RunImageJScript(Module):
    """
    Module to run ImageJ scripts via pyimagej
    """

    module_name = "RunImageJScript"
    variable_revision_number = 3
    category = "Advanced"

    doi = {"If you are using RunImageJScript please cite the following": pyimagej_link }

    def __init__(self):
        super().__init__()
        self.parsed_params = False  # Used for validation
        self.initialization_failed = False  # Used for validation

    def create_settings(self):
        module_explanation = [
            "The"
            + self.module_name
            + "module allows you to run any supported ImageJ script as part of your workflow.",
            "First, select your desired initialization method and specify the app directory or endpoint(s) if needed.",
            "Then select a script file to be executed by this module.",
            'Click the "Get parameters from script" button to detect required inputs for your script:',
            "each input will have its own setting created, allowing you to pass data from CellProfiler to ImageJ.",
            "After filling in any required inputs you can run the module normally.",
            "Note: ImageJ will only be initialized once per CellProfiler session.",
            "Note: only numeric, text and image parameters are currently supported.",
            "See also ImageJ Scripting: https://imagej.net/Scripting.",
        ]
        self.set_notes([" ".join(module_explanation)])

        self.init_choice = Choice(
            "Initialization type",
            [ijserver.INIT_LOCAL, ijserver.INIT_ENDPOINT, ijserver.INIT_LATEST],
            tooltips={
                ijserver.INIT_LOCAL: "Use a local ImageJ/Fiji installation",
                ijserver.INIT_ENDPOINT: "Specify a particular endpoint",
                ijserver.INIT_LATEST: "Use the latest Fiji, downloading if needed.",
            },
            doc="""\
Note that initialization will only occur once per CellProfiler session! After initialization, these options will be
locked for the remainder of the session.

Select the mechanism for initializing ImageJ:
 * {init_local}: Use a local Fiji or ImageJ installation
 * {init_endpoint}: Precisely specify the version of one or more components
 * {init_latest}: Use the latest Fiji version

Note that any option besides {init_local} may result in a download of the requested components.
            """.format(
                init_local=ijserver.INIT_LOCAL,
                init_endpoint=ijserver.INIT_ENDPOINT,
                init_latest=ijserver.INIT_LATEST,
            ),
        )

        self.endpoint_string = Text(
            "Initialization endpoint",
            "sc.fiji:fiji:2.1.0",
            doc="""\
Specify an initialization string as described in https://github.com/imagej/pyimagej/blob/master/doc/Initialization.md
            """,
        )

        self.initialized_method = Text(
            "Initialization type",
            value="Do not use",
            doc="""\
Indicates the method that was used to initialized ImageJ in this CellProfiler session. 
            """,
        )

        self.convert_types = Binary(
            "Adjust image type?",
            True,
            doc="""\
If enabled, ensures images are always converted to unsigned integer types when sent to ImageJ, and back to signed float types when returned to CellProfiler.
This can help common display issues by providing each application a best guess at its "expected" data type.
If you choose to disable this function, your ImageJ script will need to account for images coming in as signed float types.
            """,
        )

        init_display_string = ijbridge.init_method()
        if init_display_string:
            # ImageJ thread is already running
            self.initialized_method.set_value(init_display_string)

        self.app_directory = Directory(
            "ImageJ directory",
            allow_metadata=False,
            doc="""\
Select the folder containing the desired ImageJ/Fiji application.

{fcht}
""".format(
                fcht=IO_FOLDER_CHOICE_HELP_TEXT
            ),
        )
        if platform != "darwin":
            self.app_directory.join_parts(ABSOLUTE_FOLDER_NAME, "Fiji.app")

        def set_directory_fn_app(path):
            dir_choice, custom_path = self.app_directory.get_parts_from_path(path)
            self.app_directory.join_parts(dir_choice, custom_path)

        self.app_file = Filename(
            "Local App",
            "Fiji.app",
            doc="Select the desired app, such as Fiji.app",
            get_directory_fn=self.app_directory.get_absolute_path,
            set_directory_fn=set_directory_fn_app,
            browse_msg="Choose local application",
        )

        self.script_directory = Directory(
            "Script directory",
            allow_metadata=False,
            doc="""\
Select the folder containing the script.

{fcht}
""".format(
                fcht=IO_FOLDER_CHOICE_HELP_TEXT
            ),
        )

        def set_directory_fn_script(script_path):
            dir_choice, custom_path = self.script_directory.get_parts_from_path(
                script_path
            )
            self.script_directory.join_parts(dir_choice, custom_path)
            self.clear_script_parameters()

        self.script_file = Filename(
            "ImageJ Script",
            "script.py",
            doc="Select a script file written in any ImageJ-supported scripting language.",
            get_directory_fn=self.script_directory.get_absolute_path,
            set_directory_fn=set_directory_fn_script,
            browse_msg="Choose ImageJ script file",
        )
        self.get_parameters_button = DoSomething(
            "",
            "Get parameters from script",
            self.get_parameters_helper,
            doc="""\
Parse parameters from the currently selected script and add the appropriate settings to this CellProfiler module.

Note: this must be done each time you change the script, before running the CellProfiler pipeline!
""",
        )
        self.script_parameter_list = []
        self.script_input_settings = (
            {}
        )  # Map of input parameter names to CellProfiler settings objects
        self.script_output_settings = (
            {}
        )  # Map of output parameter names to CellProfiler settings objects
        self.script_parameter_count = HiddenCount(self.script_parameter_list)

    def get_init_string(self):
        """
        Determine if a particular initialization method has been specified. This could be a path to a local installation
        or a version string.
        """
        choice = self.init_choice.get_value()
        if choice == ijserver.INIT_LATEST:
            return None

        if choice == ijserver.INIT_LOCAL:
            init_string = self.app_directory.get_absolute_path()
            if platform == "darwin":
                init_string = path.join(init_string, self.app_file.value)
        elif choice == ijserver.INIT_ENDPOINT:
            init_string = self.endpoint_string.get_value()

        return init_string

    def clear_script_parameters(self):
        """
        Remove any existing settings added by scripts
        """
        self.script_parameter_list.clear()
        self.script_input_settings.clear()
        self.script_output_settings.clear()
        self.parsed_params = False
        self.initialization_failed = False

    def get_parameters_helper(self):
        """
        Helper method to launch get_parameters_from_script on a thread so that it isn't run on the GUI thread, since
        it may be slow (when initializing pyimagej).
        """
        # Reset previously parsed parameters
        self.clear_script_parameters()

        global stop_progress_thread
        stop_progress_thread = False

        progress_gauge = Gauge(Window.FindFocus(), -1, size=(100, -1))
        progress_gauge.Show(True)

        parse_param_thread = Thread(
            target=self.get_parameters_from_script,
            name="Parse Parameters Thread",
            daemon=True,
        )
        parse_param_thread.start()

        while True:
            # Wait for get_parameters_from_script to finish
            progress_gauge.Pulse()
            time.sleep(0.025)
            if stop_progress_thread:
                progress_gauge.Show(False)
                break

        if not self.initialization_failed:
            self.parsed_params = True

    def init_pyimagej(self):
        self.initialization_failed = False
        init_string = self.get_init_string()
        if ijbridge.init_pyimagej(init_string):
            init_display_string = self.init_choice.get_value()
            if init_display_string != ijserver.INIT_LATEST:
                init_display_string += ": " + init_string
            self.initialized_method.set_value(init_display_string)
        else:
            self.initialization_failed = True

    def get_parameters_from_script(self):
        """
        Use PyImageJ to read header text from an ImageJ script and extract inputs/outputs, which are then converted to
        CellProfiler settings for this module
        """
        global stop_progress_thread
        script_filepath = path.join(
            self.script_directory.get_absolute_path(), self.script_file.value
        )

        if not self.script_file.value or not path.exists(script_filepath):
            # nothing to do
            stop_progress_thread = True
            return

        # start the imagej server if needed
        ijbridge.start_imagej_server()

        # Start pyimagej if needed
        self.init_pyimagej()
        if self.initialization_failed == True:
            stop_progress_thread = True
            return

        # Tell pyimagej to parse the script parameters
        lock = ijbridge.lock()
        lock.acquire()
        ijbridge.to_imagej().put(
            {
                ijserver.PYIMAGEJ_KEY_COMMAND: ijserver.PYIMAGEJ_CMD_SCRIPT_PARSE,
                ijserver.PYIMAGEJ_KEY_INPUT: script_filepath,
            }
        )

        ij_return = ijbridge.from_imagej().get()
        lock.release()

        # Process pyimagej's output, converting script parameters to settings
        if ij_return != ijserver.PYIMAGEJ_STATUS_CMD_UNKNOWN:
            input_params = ij_return[ijserver.PYIMAGEJ_SCRIPT_PARSE_INPUTS]
            output_params = ij_return[ijserver.PYIMAGEJ_SCRIPT_PARSE_OUTPUTS]

            for param_dict, settings_dict, io_class in (
                (input_params, self.script_input_settings, ijserver.INPUT_CLASS),
                (output_params, self.script_output_settings, ijserver.OUTPUT_CLASS),
            ):
                for param_name in param_dict:
                    param_type = param_dict[param_name]
                    next_setting = ijserver.convert_java_type_to_setting(
                        param_name, param_type, io_class
                    )
                    if next_setting is not None:
                        settings_dict[param_name] = next_setting
                        group = SettingsGroup()
                        group.append("setting", next_setting)
                        group.append(
                            "remover",
                            RemoveSettingButton(
                                "",
                                "Remove this variable",
                                self.script_parameter_list,
                                group,
                            ),
                        )
                        add_param_info_settings(group, param_name, param_type, io_class)
                        # Each setting gets a group containing:
                        # 0 - the setting
                        # 1 - its remover
                        # 2 - (hidden) parameter name
                        # 3 - (hidden) parameter type
                        # 4 - (hidden) parameter i/o class
                        self.script_parameter_list.append(group)

            stop_progress_thread = True

    def settings(self):
        result = [
            self.script_parameter_count,
            self.init_choice,
            self.app_directory,
            self.app_file,
            self.endpoint_string,
            self.script_directory,
            self.script_file,
            self.get_parameters_button,
            self.convert_types,
        ]
        if len(self.script_parameter_list) > 0:
            result += [Divider(line=True)]
        for script_parameter_group in self.script_parameter_list:
            if isinstance(script_parameter_group.setting, Iterable):
                for s in script_parameter_group.setting:
                    result += [s]
            else:
                result += [script_parameter_group.setting]
            result += [script_parameter_group.remover]
            result += [script_parameter_group.name]
            result += [script_parameter_group.type]
            result += [script_parameter_group.io_class]

        return result

    def visible_settings(self):
        visible_settings = []

        # Update the visible settings based on the selected initialization method
        # If ImageJ is already initialized we just want to report how it was initialized
        # Otherwise we show: a string entry for "endpoint", a directory chooser for "local" (and file chooser if on mac),
        # and nothing if "latest"
        init_method = ijbridge.init_method()
        if not init_method:
            # ImageJ is not initialized yet
            visible_settings += [self.init_choice]
            input_type = self.init_choice.get_value()
            if input_type == ijserver.INIT_ENDPOINT:
                visible_settings += [self.endpoint_string]
            elif input_type == ijserver.INIT_LOCAL:
                visible_settings += [self.app_directory]
                if platform == "darwin":
                    visible_settings += [self.app_file]
        else:
            # ImageJ is initialized
            self.initialized_method.set_value(init_method)
            visible_settings += [self.initialized_method]
        visible_settings += [Divider(line=True)]
        visible_settings += [
            self.script_directory,
            self.script_file,
            self.get_parameters_button,
            self.convert_types,
        ]
        if len(self.script_parameter_list) > 0:
            visible_settings += [Divider(line=True)]
        for script_parameter in self.script_parameter_list:
            if isinstance(script_parameter.setting, Iterable):
                for s in script_parameter.setting:
                    visible_settings += [s]
            else:
                visible_settings += [script_parameter.setting]
            visible_settings += [script_parameter.remover]

        return visible_settings

    def prepare_settings(self, setting_values):
        # Start the ImageJ server here if it's not already running
        # This ensures the server is started from the main process after the
        # GUI has spun up
        ijbridge.start_imagej_server()

        settings_count = int(setting_values[0])

        if settings_count == 0:
            # No params were saved
            return

        # Params were parsed previously and saved
        self.parsed_params = True

        # Settings are stored sequentially as (value(s), remover, name, type, io_class)
        # Since some settings have multiple values for a setting we have to work backwards
        i = len(setting_values) - 1
        loaded_settings = []
        while settings_count > 0:
            group = SettingsGroup()
            # get the name, type and class
            param_name = setting_values[i - 2]
            param_type = setting_values[i - 1]
            io_class = setting_values[i]
            setting = ijserver.convert_java_type_to_setting(
                param_name, param_type, io_class
            )
            # account for remover, name, type and io_class
            i -= 4
            # account for the number of values in this setting
            if isinstance(setting, Iterable):
                i -= len(setting)
            else:
                i -= 1
            group.append("setting", setting)
            group.append(
                "remover",
                RemoveSettingButton(
                    "", "Remove this variable", self.script_parameter_list, group
                ),
            )
            add_param_info_settings(group, param_name, param_type, io_class)
            loaded_settings.append(group)
            if ijserver.INPUT_CLASS == io_class:
                self.script_input_settings[param_name] = setting
            elif ijserver.OUTPUT_CLASS == io_class:
                self.script_output_settings[param_name] = setting
            settings_count -= 1

        # add the loaded settings to our overall list, in proper order
        loaded_settings.reverse()
        for s in loaded_settings:
            self.script_parameter_list.append(s)

    def validate_module(self, pipeline):
        if self.initialization_failed:
            raise ValidationError(
                "Error starting ImageJ. Please check your initialization settings and try again.",
                self.init_choice,
            )

        no_script_msg = 'Please select a valid ImageJ script and use the "Get parameters from script" button.'

        if (
            not self.parsed_params
            or not self.script_directory
            or not self.script_file.value
        ):
            raise ValidationError(no_script_msg, self.script_file)

        script_filepath = path.join(
            self.script_directory.get_absolute_path(), self.script_file.value
        )
        if not path.exists(script_filepath):
            raise ValidationError(
                "The script you have selected is not a valid path. " + no_script_msg,
                self.script_file,
            )

        if self.init_choice.get_value() == ijserver.INIT_LOCAL:
            app_path = self.get_init_string()
            if not path.exists(app_path):
                raise ValidationError(
                    "The local application you have selected is not a valid path.",
                    self.app_directory,
                )

    def validate_module_warnings(self, pipeline):
        """Warn user if the specified FIJI executable directory is not found, and warn that a copy of FIJI will be downloaded"""
        warn_msg = 'Please note: for any initialization method except "Local", a new Fiji may be downloaded'
        " to your machine if cached dependencies not found."
        init_type = self.init_choice.get_value()
        if init_type != ijserver.INIT_LOCAL:
            # The component we attach the error to depends on if initialization has happened or not
            if not ijbridge.init_method():
                raise ValidationError(warn_msg, self.init_choice)

    def run(self, workspace):
        self.init_pyimagej()

        # Unwrap the current settings from their SettingsGroups
        all_settings = list(map(lambda x: x.settings[0], self.script_parameter_list))
        # Update the script input/output settings in case any were removed from the GUI
        self.script_input_settings = {k: v for (k,v) in self.script_input_settings.items() if v in all_settings}
        self.script_output_settings = {k: v for (k,v) in self.script_output_settings.items() if v in all_settings}

        if self.show_window:
            workspace.display_data.script_input_pixels = {}
            workspace.display_data.script_input_dimensions = {}
            workspace.display_data.script_output_pixels = {}
            workspace.display_data.script_output_dimensions = {}

        script_filepath = path.join(
            self.script_directory.get_absolute_path(), self.script_file.value
        )
        # convert the CP settings to script parameters for pyimagej
        script_inputs = {}
        for name in self.script_input_settings:
            setting = self.script_input_settings[name]
            if isinstance(setting, ImageSubscriber):
                # Images need to be pulled from the workspace
                script_inputs[name] = workspace.image_set.get_image(setting.get_value())
                if self.show_window:
                    workspace.display_data.script_input_pixels[name] = script_inputs[
                        name
                    ].pixel_data
                    workspace.display_data.script_input_dimensions[
                        name
                    ] = script_inputs[name].dimensions
            elif isinstance(setting, Iterable):
                # Currently the only supported multi-part setting is a Filename + Directory
                setting_dir = setting[0]
                setting_file = setting[1]
                script_inputs[name] = path.join(
                    setting_dir.get_absolute_path(), setting_file.value
                )
            else:
                # Other settings can be read directly
                script_inputs[name] = setting.get_value()

        # Start the script
        lock = ijbridge.lock()
        lock.acquire()
        ijbridge.to_imagej().put(
            {
                ijserver.PYIMAGEJ_KEY_COMMAND: ijserver.PYIMAGEJ_CMD_SCRIPT_RUN,
                ijserver.PYIMAGEJ_KEY_INPUT: {
                    ijserver.PYIMAGEJ_SCRIPT_RUN_FILE_KEY: script_filepath,
                    ijserver.PYIMAGEJ_SCRIPT_RUN_INPUT_KEY: script_inputs,
                    ijserver.PYIMAGEJ_SCRIPT_RUN_CONVERT_IMAGES: self.convert_types.value,
                },
            }
        )

        # Retrieve script output
        ij_return = ijbridge.from_imagej().get()
        lock.release()

        if ij_return != ijserver.PYIMAGEJ_STATUS_CMD_UNKNOWN:
            script_outputs = ij_return[ijserver.PYIMAGEJ_KEY_OUTPUT]
            for name in self.script_output_settings:
                output_key = self.script_output_settings[name].get_value()
                output_value = script_outputs[name]
                # FIXME should only do this for image outputs
                # convert back to floats for CellProfiler
                if self.convert_types.value:
                    output_value = skimage.img_as_float(output_value)
                output_image = Image(image=output_value, convert=False)
                workspace.image_set.add(output_key, output_image)
                if self.show_window:
                    workspace.display_data.script_output_pixels[
                        name
                    ] = output_image.pixel_data
                    workspace.display_data.dimensions = output_image.dimensions

    def display(self, workspace, figure):
        # TODO how do we handle differences in dimensionality between input/output images?
        figure.set_subplots(
            (
                2,
                max(
                    len(workspace.display_data.script_input_pixels),
                    len(workspace.display_data.script_output_pixels),
                ),
            ),
            dimensions=2,
        )

        i = 0
        for name in workspace.display_data.script_input_pixels:
            figure.subplot_imshow_grayscale(
                0,
                i,
                workspace.display_data.script_input_pixels[name],
                title="Input image: {}".format(name),
            )
            i += 1

        i = 0
        for name in workspace.display_data.script_output_pixels:
            figure.subplot_imshow_grayscale(
                1,
                i,
                workspace.display_data.script_output_pixels[name],
                title="Output image: {}".format(name),
                sharexy=figure.subplot(0, i),
            )
            i += 1

    def upgrade_settings(self, setting_values, variable_revision_number, module_name):
        if variable_revision_number == 1:
            # Added convert_types Binary setting
            setting_values = setting_values[:8] + [True] + setting_values[8:]
            variable_revision_number = 2
        if variable_revision_number == 2:
            # Allowed multiple settings per parameter
            # Force re-parsing of parameters
            setting_values[0] = "0"
            variable_revision_number = 3

        return setting_values, variable_revision_number
