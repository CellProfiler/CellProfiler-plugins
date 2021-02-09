from os import path

from cellprofiler_core.image import Image
from cellprofiler.modules import _help
from cellprofiler_core.module import Module
from cellprofiler_core.setting.text import Filename, ImageName, Text, Directory, Alphanumeric, Integer, Float
from cellprofiler_core.constants.module import (
    IO_FOLDER_CHOICE_HELP_TEXT,
)
from cellprofiler_core.setting import ValidationError
from cellprofiler_core.setting.do_something import DoSomething, RemoveSettingButton
from cellprofiler_core.setting._settings_group import SettingsGroup
from cellprofiler_core.setting import Divider, HiddenCount
from cellprofiler_core.setting.subscriber import ImageSubscriber
from cellprofiler_core.preferences import get_default_output_directory

from wx import Gauge
from wx import Window
from threading import Thread
import multiprocessing as mp
from multiprocessing import Process
import time
import atexit
import imagej
import jpype
import jpype.imports
from jpype.imports import *
import random
import skimage.io

"""
Constants for communicating with pyimagej
"""
pyimagej_key_command = "KEY_COMMAND"  # Matching value indicates what command to execute
pyimagej_key_input = "KEY_INPUT"  # Matching value is command-specific input object
pyimagej_key_output = "KEY_OUTPUT"  # Matching value is command-specific output object
pyimagej_key_error = "KEY_OUTPUT"  # Matching value is command-specific output object
pyimagej_cmd_script_parse = "COMMAND_SCRIPT_PARAMS"  # Parse a script file's parameters
pyimagej_script_parse_inputs = "SCRIPT_PARSE_INPUTS"  # Script input dictionary key
pyimagej_script_parse_outputs = "SCRIPT_PARSE_OUTPUTS"  # Script output dictionary key
pyimagej_cmd_script_run = "COMMAND_SCRIPT_RUN"  # Run a script
pyimagej_script_run_file_key = "SCRIPT_RUN_FILE_KEY"  # The script filename key
pyimagej_script_run_input_key = "SCRIPT_RUN_INPUT_KEY"  # The script input dictionary key
pyimagej_cmd_exit = "COMMAND_EXIT"  # Shut down the pyimagej daemon
pyimagej_status_cmd_unknown = "STATUS_COMMAND_UNKNOWN"  # Returned when an unknown command is passed to pyimagej
pyimagej_status_startup_complete = "STATUS_STARTUP_COMPLETE"  # Returned after initial startup before daemon loop


class ScriptFilename(Filename):
    """
    A helper subclass of Filename that auto-generates script parameter settings when the script changes

    optional arguments -
       value_change_fn is a function that gets called when the file value changes
    """

    def __init__(self, text, value, *args, **kwargs):
        kwargs = kwargs.copy()
        self.value_change_fn = kwargs.pop("value_change_fn", None)
        super().__init__(text, value, *args, **kwargs)

    def set_value(self, value):
        super().set_value(value)
        self.value_change_fn()


class PyimagejError(EnvironmentError):
    """
    An exception indicating that something went wrong in PyimageJ
    """

    def __init__(self, message):
        super(EnvironmentError, self).__init__(message)
        self.message = message


def convert_java_to_python_type(return_value):
    """
    Helper method to convert ImageJ/Java values to python values that can be passed between via queues (pickled)

    Parameters
    ----------
    return_value : supported Java type, required
        A value to convert from Java to python

    Returns
    ---------
    An instance of a python type that can safely cross queues with the given value, or None if no valid type exists.
    """
    type_string = str(return_value.getClass().toString()).split()[1]
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
    elif type_string == "net.imagej.Dataset" or type_string == "net.imagej.ImgPlus":
        # FIXME use pyimagej convert
        return ImageSubscriber(return_value)

    # Not a supported type
    return None


def convert_java_type_to_setting(param_name, param_type):
    """
    Helper method to convert ImageJ/Java class parameter types to CellProfiler settings

    Parameters
    ----------
    param_name : str, required
        The name of the parameter
    param_type : str, required
        The Java class name describing the parameter type

    Returns
    ---------
    A new Setting of a type appropriate for param_type, named with param_name. Or None if no valid conversion exists.
    """
    type_string = param_type.split()[1]
    if type_string == "java.lang.String" or type_string == "java.lang.Character":
        return Alphanumeric(param_name, "")
    elif type_string == "java.lang.Integer" or type_string == "java.lang.Long" or type_string == "java.lang.Short" \
            or type_string == "java.lang.Boolean" or type_string == "java.lang.Byte":
        return Integer(param_name)
    elif type_string == "java.lang.Float" or type_string == "java.lang.Double":
        return Float(param_name)
    elif type_string == "java.io.File":
        return Filename(param_name, "")
    elif type_string == "net.imagej.Dataset" or type_string == "net.imagej.ImgPlus":
        return ImageSubscriber(param_name)

    return None


def start_imagej_process(input_queue, output_queue):
    f"""Python script to run when starting a new ImageJ process.
    
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
    """
    ij = imagej.init()
    from java.io import File
    script_service = ij.script()

    # Signify output is complete
    output_queue.put(pyimagej_status_startup_complete)

    # Main daemon loop, polling the input queue
    while True:
        command_dictionary = input_queue.get()
        cmd = command_dictionary[pyimagej_key_command]
        if cmd == pyimagej_cmd_script_parse:
            script_path = command_dictionary[pyimagej_key_input]
            script_file = File(script_path)
            script_info = script_service.getScript(script_file)
            script_inputs = {}
            script_outputs = {}
            for script_in in script_info.inputs():
                script_inputs[str(script_in.getName())] = str(script_in.getType().toString())
            for script_out in script_info.outputs():
                script_outputs[str(script_out.getName())] = str(script_out.getType().toString())
            output_queue.put({pyimagej_script_parse_inputs: script_inputs,
                              pyimagej_script_parse_outputs: script_outputs})
        elif cmd == pyimagej_cmd_script_run:
            script_path = (command_dictionary[pyimagej_key_input])[pyimagej_script_run_file_key]
            script_file = File(script_path)
            input_map = (command_dictionary[pyimagej_key_input])[pyimagej_script_run_input_key]
            # FIXME probably need to convert input python types
            script_out_map = script_service.run(script_file, True, input_map).get().getOutputs()
            output_dict = {}
            for entry in script_out_map.entrySet():
                key = str(entry.getKey())
                value = convert_java_to_python_type(entry.getValue())
                if value is not None:
                    output_dict[key] = value

            output_queue.put({pyimagej_key_output: output_dict})
        elif cmd == pyimagej_cmd_exit:
            break
        else:
            output_queue.put({pyimagej_key_error: pyimagej_status_cmd_unknown})

    # Shut down the daemon
    ij.getContext().dispose()
    jpype.shutdownJVM()
    pass


class RunImageJScript(Module):
    """
    Module to run ImageJ scripts via pyimagej
    """
    module_name = "RunImageJScript"
    variable_revision_number = 1
    category = "Advanced"

    def __init__(self):
        super().__init__()
        self.imagej_process = None  # A subprocess running pyimagej
        self.to_imagej = None  # Queue to pass data to pyimagej
        self.from_imagej = None  # queue to receive data from pyimagej
        self.parsed_params = False  # Used for validation
        self.script_input_settings = {}  # Map of input parameter names to CellProfiler settings objects
        self.script_output_settings = {}  # Map of output parameter names to CellProfiler settings objects

    def create_settings(self):
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

        # TODO to auto-parse script params, change the value_change_fn to get_parameters_from_script
        self.script_file = ScriptFilename(
            "ImageJ Script", "script.py", doc="Select a script file with in any ImageJ-supported scripting language.",
            get_directory_fn=self.script_directory.get_absolute_path,
            set_directory_fn=set_directory_fn_script,
            browse_msg="Choose ImageJ script file",
            value_change_fn=self.clear_script_parameters
        )
        self.get_parameters_button = DoSomething("", 'Get parameters from script',
                                                 self.get_parameters_helper,
                                                 doc="""\
Parse parameters from the currently selected script and add the appropriate settings to this CellProfiler module.

Note: this must be done each time you change the script, before running the CellProfiler pipeline!
"""
                                                 )
        self.script_parameter_list = []
        self.script_parameter_count = HiddenCount(self.script_parameter_list)
        pass

    def settings(self):
        result = [self.script_directory, self.script_file, self.get_parameters_button]
        for script_parameter in self.script_parameter_list:
            result += [script_parameter.value]
        return result

    def visible_settings(self):
        visible_settings = [self.script_directory, self.script_file, self.get_parameters_button]
        for script_parameter in self.script_parameter_list:
            visible_settings += [script_parameter.value]
        return visible_settings

    def prepare_settings(self, setting_values):
        # TODO: Loading CP project should show the previous extracted variables when project was saved
        pass

    def close_pyimagej(self):
        if self.imagej_process is not None:
            self.to_imagej.put({pyimagej_key_command: pyimagej_cmd_exit})
        pass

    def init_pyimagej(self):
        if self.imagej_process is None:
            self.to_imagej = mp.Queue()
            self.from_imagej = mp.Queue()
            # TODO if needed we could set daemon=True
            self.imagej_process = Process(target=start_imagej_process, name="PyImageJ Daemon",
                                          args=(self.to_imagej, self.from_imagej,))
            atexit.register(self.close_pyimagej)  # TODO is there a more CP-ish way to do this?
            self.imagej_process.start()
            if self.from_imagej.get() != pyimagej_status_startup_complete:
                raise PyimagejError(
                    "PyImageJ failed to start up successfully."
                )
        pass

    def add_divider(self):
        """
        Add a divider to the settings pane
        """
        group = SettingsGroup()
        group.append("value", Divider(line=True))
        self.script_parameter_list.append(group)

    def clear_script_parameters(self):
        """
        Remove any existing settings added by scripts
        """
        self.script_parameter_list.clear()
        self.script_input_settings = {}
        self.script_output_settings = {}
        self.parsed_params = False
        pass

    def get_parameters_helper(self):
        """
        Helper method to launch get_parameters_from_script on a thread so that it isn't run on the GUI thread, since
        it may be slow (when initializing pyimagej).
        """
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
        pass

    def get_parameters_from_script(self):
        """
        Use PyImageJ to read header text from an ImageJ script and extract inputs/outputs, which are then converted to
        CellProfiler settings for this module
        """
        script_filepath = path.join(self.script_directory.get_absolute_path(), self.script_file.value)
        if not path.exists(script_filepath):
            # nothing to do
            return

        # Reset previously parsed parameters
        self.clear_script_parameters()

        # Start pyimagej if needed
        self.init_pyimagej()

        # Tell pyimagej to parse the script parameters
        self.to_imagej.put({pyimagej_key_command: pyimagej_cmd_script_parse, pyimagej_key_input: script_filepath})

        ij_return = self.from_imagej.get()

        # Process pyimagej's output
        if ij_return != pyimagej_status_cmd_unknown:
            input_params = ij_return[pyimagej_script_parse_inputs]
            output_params = ij_return[pyimagej_script_parse_outputs]

            for param_dict, settings_dict in ((input_params, self.script_input_settings),
                                              (output_params, self.script_output_settings)):
                if param_dict:
                    self.add_divider()
                for param_name in param_dict:
                    param_type = param_dict[param_name]
                    next_setting = convert_java_type_to_setting(param_name, param_type)
                    if next_setting is not None:
                        settings_dict[param_name] = next_setting
                        group = SettingsGroup()
                        group.append("value", next_setting)
                        self.script_parameter_list.append(group)

            self.parsed_params = True
            global stop_progress_thread
            stop_progress_thread = True
        pass

    def validate_module(self, pipeline):
        if not self.parsed_params:
            raise ValidationError(
                "Please select a valid ImageJ script and use the \"Get parameters from script\" button."
            )
        pass

    def run(self, workspace):
        script_filepath = path.join(self.script_directory.get_absolute_path(), self.script_file.value)

        # convert the CP settings to script parameters for pyimagej
        script_inputs = {}
        for name in self.script_input_settings:
            script_inputs[name] = self.script_input_settings[name].get_value()

        # Start the script
        self.to_imagej.put({pyimagej_key_command: pyimagej_cmd_script_run, pyimagej_key_input:
            {pyimagej_script_run_file_key: script_filepath,
             pyimagej_script_run_input_key: script_inputs}
                            })

        # Retrieve script output
        ij_return = self.from_imagej.get()
        if ij_return != pyimagej_status_cmd_unknown:
            print("command received")
            # TODO update output settings
        pass

    def display(self, workspace, figure):
        pass
