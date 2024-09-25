#################################
#
# Imports from useful Python libraries
#
#################################

import logging
import scipy.ndimage
import numpy

#################################
#
# Imports from CellProfiler
#
##################################

import cellprofiler_core.image
import cellprofiler_core.module
import cellprofiler_core.setting
from cellprofiler_core.setting import Binary

__doc__ = """\
DistanceTransform
=================

**DistanceTransform** computes the distance transform of a binary image. 
The distance of each foreground pixel is computed to the nearest background pixel. 
The resulting image is then scaled so that the largest distance is 1. 

|

============ ============ ===============
Supports 2D? Supports 3D? Respects masks?
============ ============ ===============
YES          YES          YES
============ ============ ===============

"""


class DistanceTransform(cellprofiler_core.module.ImageProcessing):
    module_name = "DistanceTransform"

    variable_revision_number = 1

    def create_settings(self):
        super(DistanceTransform, self).create_settings()

        self.rescale_values = Binary(
            "Rescale values from 0 to 1?",
            True,
            doc="""\
Select "*Yes*" to rescale the transformed values to lie between 0 and
1. This is the option to use if the distance transformed image is to be
used for thresholding by an **Identify** module or the like, which
assumes a 0-1 scaling.

Select "*No*" to leave the values in absolute pixel units. This useful
in cases where the actual pixel distances are to be used downstream as
input for a measurement module.""",
        )

    def settings(self):
        __settings__ = super(DistanceTransform, self).settings()
        __settings__ += [
            self.rescale_values,
        ]
        return __settings__

    def visible_settings(self):
        """Return the settings as displayed to the user"""
        __settings__ = super(DistanceTransform, self).settings()
        __settings__ += [self.rescale_values]
        return __settings__

    def run(self, workspace):
        x_name = self.x_name.value

        y_name = self.y_name.value

        images = workspace.image_set

        x = images.get_image(x_name)

        dimensions = x.dimensions

        x_data = x.pixel_data

        y_data = scipy.ndimage.distance_transform_edt(x_data, sampling=x.spacing)

        if self.rescale_values.value:
            y_data = y_data / numpy.max(y_data)

        y = cellprofiler_core.image.Image(
            dimensions=dimensions, image=y_data, parent_image=x
        )

        images.add(y_name, y)

        if self.show_window:
            workspace.display_data.x_data = x_data
            workspace.display_data.y_data = y_data
            workspace.display_data.dimensions = dimensions

    def volumetric(self):
        return True
