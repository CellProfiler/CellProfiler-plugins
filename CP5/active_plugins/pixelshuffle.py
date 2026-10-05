#################################
#
# Imports from useful Python libraries
#
#################################

import pathlib

#################################
#
# Imports from CellProfiler
#
##################################

import cellprofiler_core.image
import cellprofiler_core.module
import cellprofiler_core.setting
from cellprofiler_core.utilities.appose import get_environment, run_python_task

__doc__ = """\
PixelShuffle
============

**PixelShuffle** takes the intensity of each pixel in an image and it randomly shuffles its position.

The shuffle itself runs out-of-process, in an Appose-managed environment built
from the ``pixelshuffle/pixi.toml`` file shipped alongside this module - a
proof of concept for routing plugin logic through `Appose
<https://docs.apposed.org/en/latest/index.html>`__ instead of requiring the
plugin's dependencies to be importable in the main CellProfiler environment.

|

============ ============ ===============
Supports 2D? Supports 3D? Respects masks?
============ ============ ===============
YES          NO            NO
============ ============ ===============

"""

_PLUGIN_DIR = pathlib.Path(__file__).parent / "pixelshuffle"
_ENV_SPEC = _PLUGIN_DIR / "pixi.toml"
_WORKER_SCRIPT = (_PLUGIN_DIR / "_worker.py").read_text() + (
    "import appose\n"
    "import numpy\n"
    "_result = pixel_shuffle(numpy.array(x_data.ndarray()))\n"
    "_result_ndarray = appose.NDArray(dtype=_result.dtype.name, shape=list(_result.shape))\n"
    "_result_ndarray.ndarray()[:] = _result\n"
    'task.outputs["pixel_data"] = _result_ndarray\n'
)


class PixelShuffle(cellprofiler_core.module.ImageProcessing):
    module_name = "PixelShuffle"

    variable_revision_number = 1

    def settings(self):
        __settings__ = super(PixelShuffle, self).settings()
        return __settings__

    def visible_settings(self):
        """Return the settings as displayed to the user"""
        __settings__ = super(PixelShuffle, self).settings()
        return __settings__

    def run(self, workspace):
        x_name = self.x_name.value

        y_name = self.y_name.value

        images = workspace.image_set

        x = images.get_image(x_name)

        dimensions = x.dimensions

        x_data = x.pixel_data

        environment = get_environment(_ENV_SPEC)

        outputs = run_python_task(
            environment, _WORKER_SCRIPT, inputs={"x_data": x_data}
        )

        y_data = outputs["pixel_data"]

        y = cellprofiler_core.image.Image(
            dimensions=dimensions, image=y_data, parent_image=x
        )

        images.add(y_name, y)

        if self.show_window:
            workspace.display_data.x_data = x_data
            workspace.display_data.y_data = y_data
            workspace.display_data.dimensions = dimensions
