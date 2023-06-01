# coding=utf-8

"""
MergeObjects
============

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
import centrosome.cpmorphology
import skimage.morphology
import skimage.segmentation

import cellprofiler_core.image
import cellprofiler_core.module
import cellprofiler_core.setting
from cellprofiler_core.module.image_segmentation import ObjectProcessing
from cellprofiler_core.setting.choice import Choice
from cellprofiler_core.setting.text import Float

A_RELATIVE = "Relative area"
A_ABSOLUTE = "Absolute area"


class MergeObjects(ObjectProcessing):
    category = "Advanced"

    module_name = "MergeObjects"

    variable_revision_number = 2

    def create_settings(self):
        super(MergeObjects, self).create_settings()

        self.size = Float(
            text="Minimum object size",
            value=64.,
            doc="Objects smaller than this diameter will be merged with their most significant neighbor."
        )

        self.use_contact_area = cellprofiler_core.setting.Binary(
            text="Set minimum contact area threshold",
            value=False,
            doc="Use this setting for setting a minimum contact area value (either relative or absolute)"
        )

        self.contact_area_method = Choice(
            text="Minimum contact area method",
            choices=[A_ABSOLUTE, A_RELATIVE],
            value=A_ABSOLUTE,
            # TODO: This
            doc=""""""
        )

        self.abs_neighbor_size = cellprofiler_core.setting.text.Integer(
            text="Absolute minimum contact area",
            value=0,
            doc="""
When considering to merge an object, the largest neighbor must have at 
least this many bordering pixels in order to have the current object 
merge into it.

The default of 0 means no minimum is required."""
        )

        self.rel_neighbor_size = cellprofiler_core.setting.text.Float(
            text="Relative minimum contact area",
            value=0,
            minval=0,
            maxval=1,
            doc="""
When considering to merge an object, the largest neighbor must have at 
least percentage of its surface area contacting the object in order for the 
current object to merge into it.

The default of 0 means no minimum is required."""
        )

        self.plane_wise = cellprofiler_core.setting.Binary(
            text="Plane wise merge",
            value=False,
            doc="""\
Select "*{YES}*" to merge objects on a per-plane level. 
This will perform the "significant neighbor" merge on 
each plane of a volumetric image, rather than on the 
image as a whole. This may be helpful for removing seed
artifacts that are the result of segmentation.
**Note**: Plane-wise operations will be considerably slower.
""".format(**{
                "YES": "Yes"
            })
        )

        self.remove_below_threshold = cellprofiler_core.setting.Binary(
            text="Remove objects below size threshold",
            value=False,
            doc="""\
Select "*{YES}*" to ensure that objects below the minimum size
threshold with no larger significant neighbor will not be 
removed. Objects below the threshold with no neighbors are kept
by default.
""".format(**{
                "YES": "Yes"
            })
        )

    def settings(self):
        __settings__ = super(MergeObjects, self).settings()

        return __settings__ + [
            self.size,
            self.plane_wise,
            self.remove_below_threshold,
            self.use_contact_area,
            self.contact_area_method,
            self.abs_neighbor_size,
            self.rel_neighbor_size
        ]

    def visible_settings(self):
        __settings__ = super(MergeObjects, self).visible_settings()

        __settings__ += [
            self.size,
            self.plane_wise,
            self.remove_below_threshold,
            self.use_contact_area
        ]

        if self.use_contact_area.value:
            __settings__.append(self.contact_area_method)
            if self.contact_area_method.value == A_ABSOLUTE:
                __settings__.append(self.abs_neighbor_size)
            else:
                __settings__.append(self.rel_neighbor_size)

        return __settings__

    def run(self, workspace):
        self.function = lambda labels, diameter, planewise, remove_below_threshold, \
                               use_contact_area, contact_area_method, abs_neighbor_size, rel_neighbor_size: \
            merge_objects(labels, diameter, planewise, remove_below_threshold,
                          use_contact_area, contact_area_method, abs_neighbor_size, rel_neighbor_size)

        super(MergeObjects, self).run(workspace)

    def upgrade_settings(self, setting_values, variable_revision_number,
                         module_name, from_matlab):
        __settings__ = setting_values

        if variable_revision_number == 1:
            # Last few settings have changed
            __settings__ = setting_values[:5]

            # We'll assume they had an absolute neighbor size value set
            # Settings to add:
            #   use_contact_area = True
            #   contact_area_method = A_ABSOLUTE
            __settings__ += [True, A_ABSOLUTE]

            # Add the value they had for absolute size
            __settings__ += setting_values[5:]

        return __settings__, variable_revision_number, from_matlab


def _merge_neighbors(array, min_obj_size, remove_below_threshold, use_contact_area,
                     contact_area_method, abs_neighbor_size, rel_neighbor_size):
    sizes = numpy.bincount(array.ravel())
    # Set the background to zero
    sizes[0] = 0
    # Find the indices of all objects below threshold
    mask_sizes = (sizes < min_obj_size) & (sizes != 0)

    # Calculate the surface areas for each object
    if use_contact_area and contact_area_method == A_RELATIVE:
        border_mask = skimage.segmentation.find_boundaries(array, mode='inner')
        surface_areas = numpy.bincount(array[border_mask].ravel())

    merged = numpy.copy(array)

    # Iterate through each small object, determine most significant adjacent neighbor,
    # and merge the object into that neighbor
    for n in numpy.nonzero(mask_sizes)[0]:
        mask = array == n

        # "Outer" mode ensures we're only getting pixels beyond the object
        bound = skimage.segmentation.find_boundaries(mask, mode='outer')
        neighbors = numpy.bincount(array[bound].ravel())

        # If self is the largest neighbor, then "bincount" will only
        # have one entry in it - the background at index 0
        if len(neighbors) == 1:
            # If the user requests it, we should remove it from the array
            if remove_below_threshold:
                max_neighbor = 0
            # Otherwise, we don't want to modify the object
            else:
                continue

        # If there's more than one object in the neighbors array, we want
        # to set the background to zero and find the largest neighbor
        else:
            neighbors[0] = 0
            max_neighbor = numpy.argmax(neighbors)

        # Set object value to largest neighbor
        # But only if there is no minimum specified or the size is above the
        # user specified minimum
        if not use_contact_area:
            merged[merged == n] = max_neighbor
        else:
            if contact_area_method == A_ABSOLUTE:
                neighbor_size = abs_neighbor_size
                # Ensure the neighbor is above the size threshold
                conditional = neighbors[max_neighbor] > abs_neighbor_size
            else:
                neighbor_size = rel_neighbor_size
                # If the background is the largest neighbor and we want to remove, then
                # we will get a divide by zero error here
                if remove_below_threshold and max_neighbor == 0:
                    conditional = True
                else:
                    # Divide the calculated neighbor size by the total surface area
                    conditional = (float(neighbors[max_neighbor]) / surface_areas[n]) > rel_neighbor_size
            if neighbor_size == 0 or conditional:
                merged[merged == n] = max_neighbor

    return merged


def merge_objects(labels, diameter, planewise, remove_below_threshold, use_contact_area,
                  contact_area_method, abs_neighbor_size, rel_neighbor_size):
    radius = diameter / 2.0

    if labels.ndim == 2 or labels.shape[-1] in (3, 4) or planewise:
        factor = radius ** 2
    else:
        factor = (4.0 / 3.0) * (radius ** 3)

    min_obj_size = numpy.pi * factor

    # Only operate planewise if image is 3D and planewise requested
    if planewise and labels.ndim != 2 and labels.shape[-1] not in (3, 4):
        array = numpy.array([_merge_neighbors(x, min_obj_size, remove_below_threshold, use_contact_area,
                                              contact_area_method, abs_neighbor_size, rel_neighbor_size) for x in
                             labels])
    else:
        array = _merge_neighbors(labels, min_obj_size, remove_below_threshold, use_contact_area,
                                 contact_area_method, abs_neighbor_size, rel_neighbor_size)

    return centrosome.cpmorphology.relabel(array)[0]
