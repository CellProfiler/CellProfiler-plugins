# coding=utf-8

"""
ConvertOutlinesToObjects
=====================

**ConvertOutlinesToObjects** converts a binary image of outlines to objects. Contiguous regions are converted to
unique objects. Note that the background of the image will be detected as an object. Use **FilterObjects** to remove the
background region. Typically, the background object is much larger than the actual objects. Use a size threshold to
remove any large contiguous regions representing background. Occasionally, small (< 5) pixel background regions are
identified as objects. Use a size threshold to exclude any tiny contiguous regions representing background.

|

============ ============ ===============
Supports 2D? Supports 3D? Respects masks?
============ ============ ===============
YES          YES          NO
============ ============ ===============

"""

import skimage
import skimage.measure

import cellprofiler.module


class ConvertOutlinesToObjects(cellprofiler.module.ImageSegmentation):
    category = "Advanced"

    module_name = "ConvertOutlinesToObjects"

    variable_revision_number = 1

    def run(self, workspace):
        self.function = lambda x_data: skimage.measure.label(
            skimage.img_as_bool(x_data),
            background=True,
            connectivity=1
        )

        super(ConvertOutlinesToObjects, self).run(workspace)
