import numpy

import cellprofiler_core.image
import cellprofiler_core.measurement

import cellprofiler_core.setting.subscriber
import cellprofiler_core.setting.text.alphanumeric.name
from cellprofiler_core.constants.measurement import GROUP_INDEX, GROUP_NUMBER, COLTYPE_INTEGER


import cellprofiler.modules.crop
import cellprofiler_core.object
import cellprofiler_core.pipeline
import cellprofiler_core.workspace

import cellprofiler.modules.runimagejscript

INPUT_IMAGE = "input_image"
CROP_IMAGE = "crop_image"
CROP_OBJECTS = "crop_objects"
CROPPING = "cropping"
OUTPUT_IMAGE = "output_image"


def make_empty_module():
    """Return a workspace with the given image and the runimagejscript module"""
    module = cellprofiler.modules.runimagejscript.RunImageJScript()
    module.set_module_num(1)

    return module

def test_start_image_j():
    module = make_empty_module()
    module.init_pyimagej()
    module.close_pyimagej()


def test_parse_parameters():
    module = make_empty_module()

    script_filepath = "./../resources/modules/runimagejscript/dummyscript.py"
    module.get_parameters_from_script(script_filepath)

    assert len(module.script_parameter_list) > 0

    assert module.script_parameter_list[0].name.value == "image"
    assert module.script_parameter_list[1].name.value == "copy"

    assert isinstance(module.script_parameter_list[0].setting, cellprofiler_core.setting.subscriber.ImageSubscriber)
    assert isinstance(module.script_parameter_list[1].setting, cellprofiler_core.setting.text.alphanumeric.name.image_name._image_name.ImageName)


def test_invalid_script():
    pass

def test_do_nothing_to_image():
    pass

def test_do_something_to_image():
    pass

def test_multiple_output_images():
    pass