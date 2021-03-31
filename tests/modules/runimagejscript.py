import numpy

import cellprofiler_core.image
import cellprofiler_core.measurement
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


def make_workspace():
    """Return a workspace with the given image and the runimagejscript module"""
    image_set_list = cellprofiler_core.image.ImageSetList()
    image_set = image_set_list.get_image_set(0)

    module = cellprofiler.modules.runimagejscript.RunImageJScript()
    module.set_module_num(1)

    #FIXME: here set the module attributes: script directory and file

    object_set = cellprofiler_core.object.ObjectSet()

    pipeline = cellprofiler_core.pipeline.Pipeline()

    def callback(caller, event):
        assert not isinstance(event, cellprofiler_core.pipeline.event.RunException)

    pipeline.add_listener(callback)
    pipeline.add_module(module)

    m = cellprofiler_core.measurement.Measurements()

    workspace = cellprofiler_core.workspace.Workspace(
        pipeline, module, image_set, object_set, m, image_set_list
    )

    return workspace, module

def test_start_image_j():
    workspace, module = make_workspace()
    module.init_pyimagej()
    module.close_pyimagej()
    pass

def test_parse_parameters():
    pass

def test_invalid_script():
    pass

def test_do_nothing_to_image():
    pass

def test_do_something_to_image():
    pass

def test_multiple_output_images():
    pass