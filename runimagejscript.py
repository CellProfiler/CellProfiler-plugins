import itertools
import os

from cellprofiler_core.image import Image
from cellprofiler.modules import _help
from cellprofiler_core.module import Module
from cellprofiler_core.setting.text import Filename, ImageName, Text, Directory
from cellprofiler_core.constants.module import (
    IO_FOLDER_CHOICE_HELP_TEXT,
)
import multiprocessing as mp
from multiprocessing import Process
from cellprofiler_core.setting.do_something import DoSomething, RemoveSettingButton
from cellprofiler_core.setting._settings_group import SettingsGroup
from cellprofiler_core.setting import Divider, HiddenCount
from cellprofiler_core.setting.subscriber import ImageSubscriber
from cellprofiler_core.preferences import get_default_output_directory

import imagej
import jpype
import jpype.imports
from jpype.imports import *
import random
import skimage.io


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


def parse_params(script_path, queue):
    """Uses ImageJ to parse script parameters and return their names and types via the provided queue.

    Note that both name and type are returned in python string form, as Jpype Java class wrappers are not available on
    the CellProfiler side.

     Parameters
     ----------
     script_path : str, required
         Path to the ImageJ-style script file whose parameters will be read
     queue : multiprocessing.Queue, required
         A queue for cross-process communication. This will be populated with parameter {name, type} strings
     """
    ij = imagej.init()
    from java.io import File
    script_service = ij.script()
    script_file = File(script_path)
    script_info = script_service.getScript(script_file)
    for script_in in script_info.inputs():
        queue.put(str(script_in.getName()))
        queue.put(str(script_in.getType().toString()))
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

        def set_directory_fn_script(path):
            dir_choice, custom_path = self.script_directory.get_parts_from_path(path)
            self.script_directory.join_parts(dir_choice, custom_path)

        self.script_file = ScriptFilename(
            "ImageJ Script", "script.py", doc="Select a script file with in any ImageJ-supported scripting language.",
            get_directory_fn=self.script_directory.get_absolute_path,
            set_directory_fn=set_directory_fn_script,
            browse_msg="Choose ImageJ script file",
            value_change_fn=self.get_parameters_from_script
        )
        self.get_parameters_button = DoSomething("", 'Get parameters from script', self.get_parameters_from_script,
                                                 doc="""\
Parse parameters from the currently selected script and add the appropriate settings to this CellProfiler module.

Note: this must be done each time you change the script, before running the CellProfiler pipeline!
"""
                                                )
        self.script_parameter_list = []
        self.script_parameter_count = HiddenCount(self.script_parameter_list)

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

    def get_parameters_from_script(self):
        """
        Use PyImageJ to read header text from Fiji and extract input parameters.
        Probably return of list of these parameter names
        """
        script_filepath = os.path.join(self.script_directory.get_absolute_path(), self.script_file.value)
        # TODO: check that script_filepath is a valid directory
        q = mp.Queue();
        p = Process(target=parse_params, args=(script_filepath, q,))
        p.start()
        p.join()
        if not q.empty():
            self.script_parameter_list.clear()
            group = SettingsGroup()
            group.append("value", Divider(line=True))
            self.script_parameter_list.append(group)
            while not q.empty():
                group = SettingsGroup()
                param_name = q.get()
                param_type = q.get()
                #TODO use param_type to determine what kind of param to add instead of Text
                group.append("value", Text(param_name, param_type))
                self.script_parameter_list.append(group)
        pass

    def run(self, workspace):
        pass

    def display(self, workspace, figure):
        pass
