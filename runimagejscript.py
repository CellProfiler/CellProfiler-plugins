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

import multiprocessing as mp
from multiprocessing import Process
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
pyimagej_cmd_script_params = "COMMAND_SCRIPT_PARAMS"  # Parse the following script file's parameters
pyimagej_cmd_exit = "COMMAND_EXIT"  # Shut down the pyimagej daemon
pyimagej_status_running = "STATUS_RUNNING"  # Returned when a command starts running
pyimagej_status_cmd_unknown = "STATUS_COMMAND_UNKNOWN"  # Returned when an unknown command is passed to pyimagej
pyimagej_status_cmd_done = "STATUS_DONE"  # Returned when a command is complete
pyimagej_script_outputs = "BEGIN_SCRIPT_OUTPUT" # Returned after script inputs are parsed, before outputs


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


def make_equivalent_setting(param_name, param_type):
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
    if type_string == "java.lang.String":
        return Alphanumeric(param_name)
    elif type_string == "java.lang.Integer" or type_string == "java.lang.Long" or type_string == "java.lang.Short" or \
            type_string == "int" or type_string == "long" or type_string == "short":
        return Integer(param_name)
    elif type_string == "java.lang.Float" or type_string == "java.lang.Double" or type_string == "float" or \
            type_string == "double":
        return Float(param_name)
    elif type_string == "java.io.File":
        return Filename(param_name)
    elif type_string == "java.io.Directory":
        return Directory(param_name)
    elif type_string == "net.imagej.Dataset" or type_string == "net.imagej.ImgPlus":
        return ImageSubscriber(param_name)

    return None


def start_imagej_process(input_queue, output_queue):
    f"""Python script to run when starting a new ImageJ process.
    
    Note: communication is achieved by adding parameters to the from_cp queue and polling the to_cp queue: "inputs" must
    be added to the input queue after the command, while "outputs" are added to the output queue after the script starts
    
    Supported commands
    ----------
    {pyimagej_cmd_script_params} : parse the parameters from an imagej script. 
        inputs: script_filename
        outputs: parameter name/value pairs
    {pyimagej_cmd_exit} : shut down the pyimagej daemon
        inputs: none
        outputs:none
    
    Return values
    ----------
    {pyimagej_status_running} : the requested command has started successfully
    {pyimagej_status_cmd_unknown} : unrecognized command, no further output is coming
    {pyimagej_script_outputs} : Script-parsing specific - 
                                        input parsing is complete, remaining return values are script outputs

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

    # Main daemon loop, polling the input queue
    while True:
        cmd = input_queue.get()
        # The first input is always the command
        if cmd == pyimagej_cmd_script_params:
            # Indicate acceptance
            output_queue.put(pyimagej_status_running)
            script_path = input_queue.get()
            script_file = File(script_path)
            script_info = script_service.getScript(script_file)
            for script_in in script_info.inputs():
                output_queue.put(str(script_in.getName()))
                output_queue.put(str(script_in.getType().toString()))
            output_queue.put(pyimagej_script_outputs)
            for script_out in script_info.outputs():
                output_queue.put(str(script_out.getName()))
                output_queue.put(str(script_out.getType().toString()))
            output_queue.put(pyimagej_status_cmd_done)
        elif cmd == pyimagej_cmd_exit:
            break
        else:
            output_queue.put(pyimagej_status_cmd_unknown)

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
        self.imagej_process = None
        self.to_imagej = None
        self.from_imagej = None
        self.parsed_params = False
        self.script_inputs = {}
        self.script_outputs = {}

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
        self.get_parameters_button = DoSomething("", 'Get parameters from script', self.get_parameters_from_script,
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
            self.to_imagej.put(pyimagej_cmd_exit)
        pass

    def init_pyimagej(self):
        if self.imagej_process is None:
            self.to_imagej = mp.Queue()
            self.from_imagej = mp.Queue()
            # TODO if needed we could set daemon=True
            self.imagej_process = Process(target=start_imagej_process, name="PyImageJ Daemon",
                                          args=(self.to_imagej, self.from_imagej,))
            self.imagej_process.start()
            atexit.register(self.close_pyimagej)  # TODO is there a more CP-ish way to do this?
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
        self.script_inputs = {}
        self.script_outputs = {}
        self.parsed_params = False
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

        self.clear_script_parameters()

        self.init_pyimagej()

        # Tell pyimagej to parse the script parameters
        self.to_imagej.put(pyimagej_cmd_script_params)
        self.to_imagej.put(script_filepath)

        ij_return = self.from_imagej.get()

        # Process pyimagej's output
        if ij_return != pyimagej_status_cmd_unknown:
            param_dict = self.script_inputs
            added_divider = False
            while True:
                group = SettingsGroup()
                param_name = self.from_imagej.get()

                # Check if the script is done
                if param_name == pyimagej_status_cmd_done:
                    break

                # Check if input parsing is complete
                if param_name == pyimagej_script_outputs:
                    param_dict = self.script_outputs
                    group.append("value", Divider(line=True))
                    self.script_parameter_list.append(group)
                    added_divider = False
                    continue

                next_setting = make_equivalent_setting(param_name, self.from_imagej.get())
                param_dict[param_name] = next_setting
                if next_setting is not None:
                    group.append("value", next_setting)
                    if not added_divider:
                        self.add_divider()
                        added_divider = True
                    self.script_parameter_list.append(group)
            self.parsed_params = True
        pass

    def validate_module(self, pipeline):
        if not self.parsed_params:
            raise ValidationError(
                "Please select a valid ImageJ script and use the \"Get parameters from script\" button."
            )
        pass

    def run(self, workspace):
        pass

    def display(self, workspace, figure):
        pass
