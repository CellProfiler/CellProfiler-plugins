from os import path

from cellprofiler_core.image import Image
from cellprofiler_core.module import Module
from cellprofiler_core.preferences import ABSOLUTE_FOLDER_NAME
from cellprofiler_core.setting.choice import Choice
from cellprofiler_core.setting.text import Filename, Text, Directory, Alphanumeric, Integer, Float
from cellprofiler_core.setting.text.alphanumeric.name.image_name import ImageName
from cellprofiler_core.constants.module import (
    IO_FOLDER_CHOICE_HELP_TEXT,
)
from cellprofiler_core.setting import ValidationError
from cellprofiler_core.setting.do_something import DoSomething, RemoveSettingButton
from cellprofiler_core.setting._settings_group import SettingsGroup
from cellprofiler_core.setting import Divider, HiddenCount
from cellprofiler_core.setting.subscriber import ImageSubscriber

from _character import Character
from _boolean import Boolean

from wx import Gauge
from wx import Window
from threading import Thread
import multiprocessing as mp
from multiprocessing import Process
from pathlib import Path
from sys import platform
import time
import atexit
import imagej
import jpype
import random
import skimage.io

__doc__ = """\
Run ImageJ Script
=================

The **Run ImageJ Script** module allows you to run any supported ImageJ script as part
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
 
"""

"""
Constants for communicating with pyimagej
"""
PYIMAGEJ_KEY_COMMAND = "KEY_COMMAND"  # Matching value indicates what command to execute
PYIMAGEJ_KEY_INPUT = "KEY_INPUT"  # Matching value is command-specific input object
PYIMAGEJ_KEY_OUTPUT = "KEY_OUTPUT"  # Matching value is command-specific output object
PYIMAGEJ_KEY_ERROR = "KEY_OUTPUT"  # Matching value is command-specific output object
PYIMAGEJ_CMD_SCRIPT_PARSE = "COMMAND_SCRIPT_PARAMS"  # Parse a script file's parameters
PYIMAGEJ_SCRIPT_PARSE_INPUTS = "SCRIPT_PARSE_INPUTS"  # Script input dictionary key
PYIMAGEJ_SCRIPT_PARSE_OUTPUTS = "SCRIPT_PARSE_OUTPUTS"  # Script output dictionary key
PYIMAGEJ_CMD_SCRIPT_RUN = "COMMAND_SCRIPT_RUN"  # Run a script
PYIMAGEJ_SCRIPT_RUN_FILE_KEY = "SCRIPT_RUN_FILE_KEY"  # The script filename key
PYIMAGEJ_SCRIPT_RUN_INPUT_KEY = "SCRIPT_RUN_INPUT_KEY"  # The script input dictionary key
PYIMAGEJ_CMD_EXIT = "COMMAND_EXIT"  # Shut down the pyimagej daemon
PYIMAGEJ_STATUS_CMD_UNKNOWN = "STATUS_COMMAND_UNKNOWN"  # Returned when an unknown command is passed to pyimagej
PYIMAGEJ_STATUS_STARTUP_COMPLETE = "STATUS_STARTUP_COMPLETE"  # Returned after initial startup before daemon loop
PYIMAGEJ_STATUS_STARTUP_FAILED = "STATUS_STARTUP_FAILED"  # Returned when imagej.init fails
INPUT_CLASS = "INPUT"
OUTPUT_CLASS = "OUTPUT"
INIT_LOCAL = "Local"
INIT_ENDPOINT = "Endpoint"
INIT_LATEST = "Latest"

global stop_progress_thread, imagej_process, to_imagej, from_imagej, init_display_string
stop_progress_thread = False # Used to control the display of progress graphics
imagej_process = None  # A subprocess running pyimagej
to_imagej = None  # Queue to pass data to pyimagej
from_imagej = None  # queue to receive data from pyimagej
init_display_string = None # Indicator string for how imagej was initialized


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
    group.append(
        "name",
        Text(
            'Parameter name',
            param_name
        )
    )
    group.append(
        "type",
        Text(
            "Parameter type",
            param_type),
    )
    group.append(
        "io_class",
        Text(
            "Parameter classification",
            param_class),
    )


def convert_java_to_python_type(ij, return_value):
    """
    Helper method to convert ImageJ/Java values to python values that can be passed between via queues (pickled)

    Parameters
    ----------
    ij : imagej.init(), required
        ImageJ entry point
    return_value : supported Java type, required
        A value to convert from Java to python

    Returns
    ---------
    An instance of a python type that can safely cross queues with the given value, or None if no valid type exists.
    """
    if return_value is None:
        return None
    return_class = return_value.getClass()
    type_string = str(return_class.toString()).split()[1]

    image_classes = (jpype.JClass('ij.ImagePlus'), jpype.JClass('net.imagej.Dataset'), jpype.JClass('net.imagej.ImgPlus'))

    if type_string == "java.lang.String" or type_string == "java.lang.Character":
        return str(return_value)
    elif type_string == "java.lang.Integer" or type_string == "java.lang.Long" or type_string == "java.lang.Short":
        return int(return_value)
    elif type_string == "java.lang.Float" or type_string == "java.lang.Double":
        return float(return_value)
    elif type_string == "java.lang.Boolean":
        if return_value:
            return True
        else:
            return False
    elif type_string == "java.lang.Byte":
        return bytes(return_value)
    elif bool((img_class for img_class in image_classes if issubclass(return_class, img_class))):
        return ij.py.from_java(return_value)

    # Not a supported type
    return None


def convert_java_type_to_setting(param_name, param_type, param_class):
    """
    Helper method to convert ImageJ/Java class parameter types to CellProfiler settings

    Parameters
    ----------
    param_name : str, required
        The name of the parameter
    param_type : str, required
        The Java class name describing the parameter type
    param_class: str, required
        One of {input_class} or {output_class}, based on the parameter use

    Returns
    ---------
    A new Setting of a type appropriate for param_type, named with param_name. Or None if no valid conversion exists.
    """
    type_string = param_type.split()[1]
    img_strings = ("ij.ImagePlus", "net.imagej.Dataset", "net.imagej.ImgPlus")
    if INPUT_CLASS == param_class:
        param_label = param_name
        if type_string == "java.lang.String":
            return Alphanumeric(param_label, "")
        if type_string == "java.lang.Character":
            return Character(param_label, "")
        elif type_string == "java.lang.Integer":
            return Integer(param_label, 0, minval=-2 ** 31, maxval=((2 ** 31) - 1))
        elif type_string == "java.lang.Long":
            return Integer(param_label, 0, minval=-2 ** 63, maxval=((2 ** 63) - 1))
        elif type_string == "java.lang.Short":
            return Integer(param_label, 0, minval=-32768, maxval=32767)
        elif type_string == "java.lang.Byte":
            return Integer(param_label, 0, minval=-128, maxval=127)
        elif type_string == "java.lang.Boolean":
            return Boolean(param_label, 0)
        elif type_string == "java.lang.Float":
            return Float(param_label, minval=-2 ** 31, maxval=((2 ** 31) - 1))
        elif type_string == "java.lang.Double":
            return Float(param_label, minval=-2 ** 63, maxval=((2 ** 63) - 1))
        elif type_string == "java.io.File":
            return Filename(param_label, "")
        elif bool((img_string for img_string in img_strings if type_string == img_string)):
            return ImageSubscriber(param_label)
    elif OUTPUT_CLASS == param_class:
        if bool((img_string for img_string in img_strings if type_string == img_string)):
            return ImageName("[OUTPUT, " + type_string + "] " + param_name, param_name, doc=
            """
            You may use this setting to rename the indicated output variable, if desired.
            """
                             )

    return None


def preprocess_script_inputs(ij, input_map):
    """Helper method to convert pythonic inputs to something that can be handled by ImageJ

    In particular this is necessary for image inputs which won't be auto-converted by Jpype

    Parameters
    ----------
    ij : imagej.init(), required
        ImageJ entry point (from imagej.init())
    input_map:
        map of input names to values
    """
    for key in input_map:
        if isinstance(input_map[key], Image):
            input_map[key] = ij.py.to_dataset(input_map[key].get_image())


def start_imagej_process(input_queue, output_queue, init_string):
    """Python script to run when starting a new ImageJ process.
    
    All commands are initiated by adding a dictionary with a {pyimagej_key_command} entry to the {input_queue}. This
    indicating which supported command should be executed. Some commands may take additional input, which is specified
    in the dictionary with {pyimagej_key_input}.

    Outputs are returned by adding a dictionary to the {output_queue} with the {pyimagej_key_output} key, or
    {pyimagej_key_error} if an error occurred during script execution.
    
    Supported commands
    ----------
    {pyimagej_cmd_script_parse} : parse the parameters from an imagej script. 
        inputs: script filename
        outputs: dictionary with mappings
            {pyimagej_script_parse_inputs} -> dictionary of input field name/value pairs
            {pyimagej_script_parse_outputs} -> dictionary of output field name/value pairs
    {pyimagej_cmd_script_run} : takes a set of named inputs from CellProfiler and runs the given imagej script
        inputs: dictionary with mappings
            {pyimagej_script_run_file_key} -> script filename
            {pyimagej_script_run_input_key} -> input parameter name/value dictionary
        outputs: dictionary containing output field name/value pairs
    {pyimagej_cmd_exit} : shut down the pyimagej daemon.
        inputs: none
        outputs: none
    
    Return values
    ----------
    {pyimagej_status_cmd_unknown} : unrecognized command, no further output is coming

    Parameters
    ----------
    input_queue : multiprocessing.Queue, required
        This Queue will be polled for input commands to run through ImageJ
    output_queue : multiprocessing.Queue, required
        This Queue will be filled with outputs to return to CellProfiler
    init_string : str, optional
        This can be a path to a local ImageJ installation, or an initialization string per imagej.init(),
        e.g. sc.fiji:fiji:2.1.0
    """

    ij = False

    try:
        if init_string:
            # Attempt to initialize with the given string
            ij = imagej.init(init_string)
        else:
            ij = imagej.init()
    except jpype.JException as ex:
        # Initialization failed
        output_queue.put(PYIMAGEJ_STATUS_STARTUP_FAILED)
        jpype.shutdownJVM()
        return

    script_service = ij.script()

    # Signify output is complete
    output_queue.put(PYIMAGEJ_STATUS_STARTUP_COMPLETE)

    # Main daemon loop, polling the input queue
    while True:
        command_dictionary = input_queue.get()
        cmd = command_dictionary[PYIMAGEJ_KEY_COMMAND]
        if cmd == PYIMAGEJ_CMD_SCRIPT_PARSE:
            script_path = command_dictionary[PYIMAGEJ_KEY_INPUT]
            script_file = Path(script_path)
            script_info = script_service.getScript(script_file)
            script_inputs = {}
            script_outputs = {}
            for script_in in script_info.inputs():
                script_inputs[str(script_in.getName())] = str(script_in.getType().toString())
            for script_out in script_info.outputs():
                script_outputs[str(script_out.getName())] = str(script_out.getType().toString())
            output_queue.put({PYIMAGEJ_SCRIPT_PARSE_INPUTS: script_inputs,
                              PYIMAGEJ_SCRIPT_PARSE_OUTPUTS: script_outputs})
        elif cmd == PYIMAGEJ_CMD_SCRIPT_RUN:
            script_path = (command_dictionary[PYIMAGEJ_KEY_INPUT])[PYIMAGEJ_SCRIPT_RUN_FILE_KEY]
            script_file = Path(script_path)
            input_map = (command_dictionary[PYIMAGEJ_KEY_INPUT])[PYIMAGEJ_SCRIPT_RUN_INPUT_KEY]
            preprocess_script_inputs(ij, input_map)
            script_out_map = script_service.run(script_file, True, input_map).get().getOutputs()
            output_dict = {}
            for entry in script_out_map.entrySet():
                key = str(entry.getKey())
                value = convert_java_to_python_type(ij, entry.getValue())
                if value is not None:
                    output_dict[key] = value

            output_queue.put({PYIMAGEJ_KEY_OUTPUT: output_dict})
        elif cmd == PYIMAGEJ_CMD_EXIT:
            break
        else:
            output_queue.put({PYIMAGEJ_KEY_ERROR: PYIMAGEJ_STATUS_CMD_UNKNOWN})

    # Shut down the daemon
    ij.getContext().dispose()
    jpype.shutdownJVM()


class RunImageJScript(Module):
    """
    Module to run ImageJ scripts via pyimagej
    """
    module_name = "RunImageJScript"
    variable_revision_number = 1
    category = "Advanced"

    def __init__(self):
        super().__init__()
        self.parsed_params = False  # Used for validation
        self.initialization_failed = False  # Used for validation

    def create_settings(self):
        module_explanation = [
            "The" + self.module_name + "module allows you to run any supported ImageJ script as part of your workflow.",
            "First, select your desired initialization method and specify the app directory or endpoint(s) if needed.",
            "Then select a script file to be executed by this module.",
            "Click the \"Get parameters from script\" button to detect required inputs for your script:",
            "each input will have its own setting created, allowing you to pass data from CellProfiler to ImageJ.",
            "After filling in any required inputs you can run the module normally.",
            "Note: ImageJ will only be initialized once per CellProfiler session.",
            "Note: only numeric, text and image parameters are currently supported.",
            "See also ImageJ Scripting: https://imagej.net/Scripting."

        ]
        self.set_notes([" ".join(module_explanation)])

        self.init_choice = Choice(
            "Initialization type", [INIT_LOCAL, INIT_ENDPOINT, INIT_LATEST],
            tooltips={INIT_LOCAL: "Use a local ImageJ/Fiji installation", INIT_ENDPOINT: "Specify a particular endpoint",
                      INIT_LATEST: "Use the latest Fiji, downloading if needed."},
            doc="""\
Note that initialization will only occur once per CellProfiler session! After initialization, these options will be
locked for the remainder of the session.

Select the mechanism for initializing ImageJ:
 * {init_local}: Use a local Fiji or ImageJ installation
 * {init_endpoint}: Precisely specify the version of one or more components
 * {init_latest}: Use the latest Fiji version

Note that any option besides {init_local} may result in a download of the requested components.
            """.format(
                init_local=INIT_LOCAL,
                init_endpoint=INIT_ENDPOINT,
                init_latest=INIT_LATEST,
            ),
        )

        self.endpoint_string = Text(
            "Initialization endpoint", "sc.fiji:fiji:2.1.0", doc="""\
Specify an initialization string as described in https://github.com/imagej/pyimagej/blob/master/doc/Initialization.md
            """,
        )

        self.initialized_method = Text("Initialization type", value="Do not use", doc="""\
Indicates the method that was used to initialized ImageJ in this CellProfiler session. 
            """,
        )
        global init_display_string
        if init_display_string:
            # ImageJ thread is already running
            self.initialized_method.set_value(init_display_string)

        self.app_directory = Directory(
            "ImageJ directory", allow_metadata=False, doc="""\
Select the folder containing the desired ImageJ/Fiji application.

{fcht}
""".format(
                fcht=IO_FOLDER_CHOICE_HELP_TEXT
            ),
        )
        if platform != 'darwin':
            self.app_directory.join_parts(ABSOLUTE_FOLDER_NAME, "Fiji.app")

        def set_directory_fn_app(path):
            dir_choice, custom_path = self.app_directory.get_parts_from_path(path)
            self.app_directory.join_parts(dir_choice, custom_path)

        self.app_file = Filename(
            "Local App", "Fiji.app", doc="Select the desired app, such as Fiji.app",
            get_directory_fn=self.app_directory.get_absolute_path,
            set_directory_fn=set_directory_fn_app,
            browse_msg="Choose local application"
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
            dir_choice, custom_path = self.script_directory.get_parts_from_path(script_path)
            self.script_directory.join_parts(dir_choice, custom_path)
            self.clear_script_parameters()

        self.script_file = Filename(
            "ImageJ Script", "script.py", doc="Select a script file written in any ImageJ-supported scripting language.",
            get_directory_fn=self.script_directory.get_absolute_path,
            set_directory_fn=set_directory_fn_script,
            browse_msg="Choose ImageJ script file",
        )
        self.get_parameters_button = DoSomething("", 'Get parameters from script',
                                                 self.get_parameters_helper,
                                                 doc="""\
Parse parameters from the currently selected script and add the appropriate settings to this CellProfiler module.

Note: this must be done each time you change the script, before running the CellProfiler pipeline!
"""
                                                 )
        self.script_parameter_list = []
        self.script_input_settings = {}  # Map of input parameter names to CellProfiler settings objects
        self.script_output_settings = {}  # Map of output parameter names to CellProfiler settings objects
        self.script_parameter_count = HiddenCount(self.script_parameter_list)

    def get_init_string(self):
        """
        Determine if a particular initialization method has been specified. This could be a path to a local installation
        or a version string.
        """
        choice = self.init_choice.get_value()
        if choice == INIT_LATEST:
            return None

        if choice == INIT_LOCAL:
            init_string = self.app_directory.get_absolute_path()
            if platform == 'darwin':
                init_string = path.join(init_string, self.app_file.value)
        elif choice == INIT_ENDPOINT:
            init_string = self.endpoint_string.get_value()

        return init_string

    def close_pyimagej(self):
        """
        Close the pyimagej daemon thread
        """
        global imagej_process, to_imagej
        if imagej_process is not None:
            to_imagej.put({PYIMAGEJ_KEY_COMMAND: PYIMAGEJ_CMD_EXIT})

    def init_pyimagej(self):
        """
        Start the pyimagej daemon thread if it isn't already running.
        """
        self.initialization_failed = False
        init_string = self.get_init_string()

        global imagej_process, to_imagej, from_imagej, init_display_string
        if imagej_process is None:
            to_imagej = mp.Queue()
            from_imagej = mp.Queue()
            # TODO if needed we could set daemon=True
            imagej_process = Process(target=start_imagej_process, name="PyImageJ Daemon",
                                          args=(to_imagej, from_imagej, init_string,))
            imagej_process.start()
            result = from_imagej.get()
            if result == PYIMAGEJ_STATUS_STARTUP_FAILED:
                imagej_process = None
                self.initialization_failed = True
            else:
                atexit.register(self.close_pyimagej)  # TODO is there a more CP-ish way to do this?
                init_display_string = self.init_choice.get_value()
                if init_display_string != INIT_LATEST:
                    init_display_string += ": " + init_string
                self.initialized_method.set_value(init_display_string)

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

        parse_param_thread = Thread(target=self.get_parameters_from_script, name="Parse Parameters Thread", daemon=True)
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

    def get_parameters_from_script(self):
        """
        Use PyImageJ to read header text from an ImageJ script and extract inputs/outputs, which are then converted to
        CellProfiler settings for this module
        """
        global stop_progress_thread, imagej_process, to_imagej, from_imagej
        script_filepath = path.join(self.script_directory.get_absolute_path(), self.script_file.value)

        if not self.script_file.value or not path.exists(script_filepath):
            # nothing to do
            stop_progress_thread = True
            return

        # Start pyimagej if needed
        self.init_pyimagej()
        if not imagej_process:
            stop_progress_thread = True
            return

        # Tell pyimagej to parse the script parameters
        to_imagej.put({PYIMAGEJ_KEY_COMMAND: PYIMAGEJ_CMD_SCRIPT_PARSE, PYIMAGEJ_KEY_INPUT: script_filepath})

        ij_return = from_imagej.get()

        # Process pyimagej's output, converting script parameters to settings
        if ij_return != PYIMAGEJ_STATUS_CMD_UNKNOWN:
            input_params = ij_return[PYIMAGEJ_SCRIPT_PARSE_INPUTS]
            output_params = ij_return[PYIMAGEJ_SCRIPT_PARSE_OUTPUTS]

            for param_dict, settings_dict, io_class in ((input_params, self.script_input_settings, INPUT_CLASS),
                                                        (output_params, self.script_output_settings, OUTPUT_CLASS)):
                for param_name in param_dict:
                    param_type = param_dict[param_name]
                    next_setting = convert_java_type_to_setting(param_name, param_type, io_class)
                    if next_setting is not None:
                        settings_dict[param_name] = next_setting
                        group = SettingsGroup()
                        group.append("setting", next_setting)
                        group.append("remover", RemoveSettingButton("", "Remove this variable",
                                                                    self.script_parameter_list, group))
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
        result = [self.script_parameter_count, self.init_choice, self.app_directory, self.app_file, self.endpoint_string, self.script_directory, self.script_file, self.get_parameters_button]
        if len(self.script_parameter_list) > 0:
            result += [Divider(line=True)]
        for script_parameter_group in self.script_parameter_list:
            result += [script_parameter_group.setting]
            result += [script_parameter_group.remover]
            result += [script_parameter_group.name]
            result += [script_parameter_group.type]
            result += [script_parameter_group.io_class]

        return result

    def visible_settings(self):
        visible_settings = []
        global imagej_process

        # Update the visible settings based on the selected initialization method
        # If ImageJ is already initialized we just want to report how it was initialized
        # Otherwise we show: a string entry for "endpoint", a directory chooser for "local" (and file chooser if on mac),
        # and nothing if "latest"
        if not imagej_process:
            visible_settings += [self.init_choice]
            input_type = self.init_choice.get_value()
            # ImageJ is not initialized yet
            if input_type == INIT_ENDPOINT:
                visible_settings += [self.endpoint_string]
            elif input_type == INIT_LOCAL:
                visible_settings += [self.app_directory]
                if platform == 'darwin':
                    visible_settings += [self.app_file]
        else:
            # ImageJ is initialized
            visible_settings += [self.initialized_method]

        visible_settings += [Divider(line=True)]
        visible_settings += [self.script_directory, self.script_file, self.get_parameters_button]
        if len(self.script_parameter_list) > 0:
            visible_settings += [Divider(line=True)]
        for script_parameter in self.script_parameter_list:
            visible_settings += [script_parameter.setting]
            visible_settings += [script_parameter.remover]

        return visible_settings

    def prepare_settings(self, setting_values):
        settings_count = int(setting_values[0])

        if settings_count == 0:
            # No params were saved
            return

        # Params were parsed previously and saved
        self.parsed_params = True

        # Looking at the last 5N elements will give the us (value, remover, name, type, io_class) for the N settings
        # We care about the name and type information, since this goes in one of our settings
        settings_info = setting_values[-settings_count * 5:]
        for i in range(0, len(settings_info), 5):
            group = SettingsGroup()
            param_name = settings_info[i + 2]
            param_type = settings_info[i + 3]
            io_class = settings_info[i + 4]
            setting = convert_java_type_to_setting(param_name, param_type, io_class)
            group.append("setting", setting)
            group.append("remover", RemoveSettingButton("", "Remove this variable", self.script_parameter_list, group))
            add_param_info_settings(group, param_name, param_type, io_class)
            self.script_parameter_list.append(group)
            if INPUT_CLASS == io_class:
                self.script_input_settings[param_name] = setting
            elif OUTPUT_CLASS == io_class:
                self.script_output_settings[param_name] = setting

    def validate_module(self, pipeline):
        if self.initialization_failed:
            raise ValidationError(
                "Error starting ImageJ. Please check your initialization settings and try again.",
                self.init_choice
            )

        no_script_msg = "Please select a valid ImageJ script and use the \"Get parameters from script\" button."

        if not self.parsed_params or not self.script_directory or not self.script_file.value:
            raise ValidationError(
                no_script_msg,
                self.script_file
            )

        script_filepath = path.join(self.script_directory.get_absolute_path(), self.script_file.value)
        if not path.exists(script_filepath):
            raise ValidationError(
                "The script you have selected is not a valid path. " + no_script_msg,
                self.script_file
            )

        if self.init_choice.get_value() == INIT_LOCAL:
            app_path = self.get_init_string()
            if not path.exists(app_path):
                raise ValidationError(
                    "The local application you have selected is not a valid path.",
                    self.app_directory
                )

    def validate_module_warnings(self, pipeline):
        global imagej_process
        """Warn user if the specified FIJI executable directory is not found, and warn that a copy of FIJI will be downloaded"""
        warn_msg = "Please note: any initialization method except \"Local\", a new Fiji may be downloaded"
        " to your machine if cached dependencies not found."
        init_type = self.init_choice.get_value()
        if init_type != INIT_LOCAL:
            # The component we attach the error to depends on if initialization has happened or not
            if not imagej_process:
                raise ValidationError(warn_msg, self.init_choice)
            else:
                raise ValidationError(warn_msg + " If re-initialization is required, please restart CellProfiler.",
                                      self.initialized_method)


    def run(self, workspace):
        self.init_pyimagej()

        if self.show_window:
            workspace.display_data.script_input_pixels = {}
            workspace.display_data.script_input_dimensions = {}
            workspace.display_data.script_output_pixels = {}
            workspace.display_data.script_output_dimensions = {}

        script_filepath = path.join(self.script_directory.get_absolute_path(), self.script_file.value)
        # convert the CP settings to script parameters for pyimagej
        script_inputs = {}
        for name in self.script_input_settings:
            setting = self.script_input_settings[name]
            if isinstance(setting, ImageSubscriber):
                # Images need to be pulled from the workspace
                script_inputs[name] = workspace.image_set.get_image(setting.get_value())
                if self.show_window:
                    workspace.display_data.script_input_pixels[name] = script_inputs[name].pixel_data
                    workspace.display_data.script_input_dimensions[name] = script_inputs[name].dimensions
            else:
                # Other settings can be read directly
                script_inputs[name] = setting.get_value()

        # Start the script
        to_imagej.put({PYIMAGEJ_KEY_COMMAND: PYIMAGEJ_CMD_SCRIPT_RUN, PYIMAGEJ_KEY_INPUT:
            {PYIMAGEJ_SCRIPT_RUN_FILE_KEY: script_filepath,
             PYIMAGEJ_SCRIPT_RUN_INPUT_KEY: script_inputs}
                            })

        # Retrieve script output
        ij_return = from_imagej.get()
        if ij_return != PYIMAGEJ_STATUS_CMD_UNKNOWN:
            script_outputs = ij_return[PYIMAGEJ_KEY_OUTPUT]
            for name in self.script_output_settings:
                output_key = self.script_output_settings[name].get_value()
                output_value = script_outputs[name]
                output_image = Image(image=output_value, convert=False)
                workspace.image_set.add(output_key, output_image)
                if self.show_window:
                    workspace.display_data.script_output_pixels[name] = output_image.pixel_data
                    workspace.display_data.dimensions = output_image.dimensions

    def display(self, workspace, figure):
        # TODO how do we handle differences in dimensionality between input/output images?
        figure.set_subplots((2, max(len(workspace.display_data.script_input_pixels),
                                    len(workspace.display_data.script_output_pixels))), dimensions=2)

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
            )
            i += 1
