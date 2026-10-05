#################################
#
# Imports from useful Python libraries
#
#################################

import logging
import scipy.ndimage
import numpy
import random

#################################
#
# Imports from CellProfiler
#
##################################

import cellprofiler_core.image
import cellprofiler_core.module
import cellprofiler_core.setting

__doc__ = """\
PixelShuffle
============

**PixelShuffle** takes the intensity of each pixel in an image and it randomly shuffles its position.

|

============ ============ ===============
Supports 2D? Supports 3D? Respects masks?
============ ============ ===============
YES          NO            NO
============ ============ ===============

"""


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

        shape = numpy.array(x_data.shape).astype(int)

        pxs = []
        width, height = shape[:2]
        for w in range(width):
            for h in range(height):
                pxs.append(x_data[w, h])
        idx = list(range(len(pxs)))
        random.shuffle(idx)
        seq = []
        for i in idx:
            seq.append(pxs[i])
        out = numpy.asarray(seq)
        out = out.reshape(width, height)

        y_data = out

        y = cellprofiler_core.image.Image(
            dimensions=dimensions, image=y_data, parent_image=x
        )

        images.add(y_name, y)

        if self.show_window:
            workspace.display_data.x_data = x_data
            workspace.display_data.y_data = y_data
            workspace.display_data.dimensions = dimensions
