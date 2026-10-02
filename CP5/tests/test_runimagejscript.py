import numpy

import cellprofiler_core.image
import cellprofiler_core.measurement

import cellprofiler_core.setting.subscriber
import cellprofiler_core.setting.text.alphanumeric

from cellprofiler_core.setting.text import Directory, Filename


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
    pipeline = cellprofiler_core.pipeline.Pipeline()

    module = cellprofiler.modules.runimagejscript.RunImageJScript()
    module.set_module_num(1)
    image_set_list = cellprofiler_core.image.ImageSetList()
    image_set = image_set_list.get_image_set(0)

    object_set = cellprofiler_core.object.ObjectSet()

    def callback(caller, event):
        assert not isinstance(event, cellprofiler_core.pipeline.event.RunException)

    pipeline.add_listener(callback)
    pipeline.add_module(module)
    m = cellprofiler_core.measurement.Measurements()

    workspace = cellprofiler_core.workspace.Workspace(
        pipeline, module, image_set, object_set, m, image_set_list
    )

    return module, workspace

def test_start_image_j():
    module, workspace = make_workspace()
    module.init_pyimagej()
    module.close_pyimagej()


def test_parse_parameters():
    module, workspace = make_workspace()

    module.script_directory = Directory(
        "Script directory")
    module.script_file = Filename(
        "ImageJ Script", "./../resources/modules/runimagejscript/dummyscript.py")
    module.get_parameters_from_script()

    assert len(module.script_parameter_list) > 0

    assert module.script_parameter_list[0].name.value == "image"
    assert module.script_parameter_list[1].name.value == "copy"

    assert isinstance(module.script_parameter_list[0].setting, cellprofiler_core.setting.subscriber.ImageSubscriber)
    assert isinstance(module.script_parameter_list[1].setting, cellprofiler_core.setting.text.alphanumeric.name.image_name._image_name.ImageName)

def test_copy_image():
    x, y = numpy.mgrid[0:10, 0:10]
    input_image = (x / 100.0 + y / 10.0).astype(numpy.float32)

    module, workspace = make_workspace()

    module.script_directory = Directory(
        "Script directory")
    module.script_file = Filename(
        "ImageJ Script", "./../resources/modules/runimagejscript/dummyscript.py")
    module.get_parameters_from_script()

    workspace.image_set.add("None", cellprofiler_core.image.Image(input_image))

    module.run(workspace)

    output_image = workspace.image_set.get_image("copy")

    assert numpy.all(output_image.pixel_data == input_image)