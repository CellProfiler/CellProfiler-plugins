# coding=utf-8

"""
MergeObjects
===========

**MergeObjects** merges objects below a certain threshold into its most prevalent, adjacent neighbor.

**MergeObjects** can be run *after* any labeling or segmentation module (e.g.,
**ConvertImageToObjects** or **Watershed**). Labels are preserved and, where possible, small
objects are merged into neighboring objects that constitute a majority of the small object's
border. This can be useful for reversing over-segmentation and artifacts that might result
from seeding operations.

|

============ ============ ===============
Supports 2D? Supports 3D? Respects masks?
============ ============ ===============
YES          YES          NO
============ ============ ===============

"""

import numpy
import skimage.morphology
import skimage.segmentation

import cellprofiler.image
import cellprofiler.module
import cellprofiler.setting


class MergeObjects(cellprofiler.module.ObjectProcessing):
    category = "Advanced"

    module_name = "MergeObjects"

    variable_revision_number = 1

    def create_settings(self):
        super(MergeObjects, self).create_settings()

        self.size = cellprofiler.setting.Float(
            text="Minimum object size",
            value=64.,
            doc="Objects smaller than this diameter will be merged with their most significant neighbor."
        )

        self.slice_wise = cellprofiler.setting.Binary(
            text="Slice wise merge",
            value=False,
            doc="""\
Select "*{YES}*" to merge objects on a per-slice level. 
This will perform the "significant neighbor" merge on 
each slice of a volumetric image, rather than on the 
image as a whole. This may be helpful for removing seed
artifacts that are the result of segmentation.
**Note**: Slice-wise operations will be considerably slower.
""".format(**{
                "YES": cellprofiler.setting.YES
            })
        )

        self.remove_below_threshold = cellprofiler.setting.Binary(
            text="Remove objects below size threshold",
            value=False,
            doc="""\
Select "*{YES}*" to ensure that objects below the minimum size
threshold with no larger significant neighbor will not be 
removed. Objects below the threshold with no neighbors are kept
by default.
""".format(**{
                "YES": cellprofiler.setting.YES
            })
        )

    def settings(self):
        __settings__ = super(MergeObjects, self).settings()

        return __settings__ + [
            self.size,
            self.slice_wise,
            self.remove_below_threshold
        ]

    def visible_settings(self):
        __settings__ = super(MergeObjects, self).visible_settings()

        return __settings__ + [
            self.size,
            self.slice_wise,
            self.remove_below_threshold
        ]

    def run(self, workspace):
        self.function = lambda labels, diameter, slicewise, remove_below_threshold: \
            merge_objects(labels, diameter, slicewise, remove_below_threshold)

        super(MergeObjects, self).run(workspace)


def _merge_neighbors(array, min_obj_size, remove_below_threshold):
    sizes = numpy.bincount(array.ravel())
    # Find the indices of all objects below threshold
    mask_sizes = (sizes < min_obj_size) & (sizes != 0)

    merged = numpy.copy(array)

    # Iterate through each small object, determine most significant adjacent neighbor,
    # and merge the object into that neighbor
    for n in numpy.nonzero(mask_sizes)[0]:
        mask = array == n

        # "Outer" mode ensures we're only getting pixels beyond the object
        bound = skimage.segmentation.find_boundaries(mask, mode='outer')
        neighbors = numpy.bincount(array[bound].ravel())

        # If self is the largest neighbor, then "bincount" will only
        # have one entry in it - the backround at index 0
        if len(neighbors) == 1:
            # If the user requests it, we should remove it from the array
            if remove_below_threshold:
                max_neighbor = 0
            # Otherwise, we don't want to modify the object
            else:
                max_neighbor = n

        # Otherwise, we want to set the background to zero and
        # find the largest neighbor
        else:
            neighbors[0] = 0
            max_neighbor = numpy.argmax(neighbors)

        # Set object value to largest neighbor
        merged[merged == n] = max_neighbor
    return merged


def merge_objects(labels, diameter, slicewise, remove_below_threshold):
    radius = diameter / 2.0

    if labels.ndim == 2 or labels.shape[-1] in (3, 4) or slicewise:
        factor = radius ** 2
    else:
        factor = (4.0 / 3.0) * (radius ** 3)

    min_obj_size = numpy.pi * factor

    # Only operate slicewise if image is 3D and slicewise requested
    if slicewise and labels.ndim != 2 and labels.shape[-1] not in (3, 4):
        return numpy.array([_merge_neighbors(x, min_obj_size, remove_below_threshold) for x in labels])
    return _merge_neighbors(labels, min_obj_size, remove_below_threshold)
