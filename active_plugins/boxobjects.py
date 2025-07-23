from cellprofiler_core.module import Module
from cellprofiler_core.setting import Binary
from cellprofiler_core.setting.choice import Choice
from cellprofiler_core.setting.subscriber import LabelSubscriber
from cellprofiler_core.setting.text import LabelName, Integer
from cellprofiler_core.setting import Measurement
from cellprofiler_core.utilities.core.module.identify import (
    add_object_location_measurements,
    add_object_count_measurements,
    get_object_measurement_columns,
)

from cellprofiler_library.modules import expand_or_shrink_objects, measureobjectsizeshape
from cellprofiler_library.opts.objectsizeshapefeatures import ObjectSizeShapeFeatures
from cellprofiler_library.functions.measurement import measure_object_size_shape
from cellprofiler.modules import _help

__doc__ = """\
ExpandOrShrinkObjects
=====================

**ExpandOrShrinkObjects** expands or shrinks objects by a defined
distance.

The module expands or shrinks objects by adding or removing border
pixels. You can specify a certain number of border pixels to be added or
removed, expand objects until they are almost touching, or shrink objects
down to a point. The module can also separate touching objects without
otherwise shrinking them, and can perform some specialized morphological
operations that remove pixels without completely removing an object.

See also **IdentifySecondaryObjects** which allows creating new objects
based on expansion of existing objects, with a a few different options
than in this module. There are also several related modules in the
*Advanced* category (e.g., **Dilation**, **Erosion**,
**MorphologicalSkeleton**).

{HELP_ON_SAVING_OBJECTS}

|

============ ============ ===============
Supports 2D? Supports 3D? Respects masks?
============ ============ ===============
YES          NO           YES
============ ============ ===============

Measurements made by this module
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Image measurements:**

-  *Count:* Number of expanded/shrunken objects in the image.

**Object measurements:**

-  *Location\_X, Location\_Y:* Pixel (*X,Y*) coordinates of the center
   of mass of the expanded/shrunken objects.
""".format(
    **{"HELP_ON_SAVING_OBJECTS": _help.HELP_ON_SAVING_OBJECTS}
)

import centrosome.cpmorphology
import numpy
import scipy.ndimage
import skimage
import cellprofiler_core.object

O_ASSIGN_ARBITRARY = "Let the first box get the overlapping region"
O_ALLOW_OVERLAP = "Allow overlap between boxes"
O_FIX_OVERLAP = "Resolve overlap between boxes"


library_mapping = {
    O_ASSIGN_ARBITRARY: 'assign_arbitrary',
    O_ALLOW_OVERLAP:'allow_overlap',
    O_FIX_OVERLAP:'fix_overlap'    
}

O_ALL = list(library_mapping.keys())

class CreateBoundingBoxObject(Module):
    module_name = "CreateBoundingBoxObject"
    category = "Object Processing"
    variable_revision_number = 1

    def create_settings(self):
        self.object_name = LabelSubscriber(
            "Select the input objects",
            "None",
            doc="Select the objects that you want to create bounding boxes for",
        )

        self.output_object_name = LabelName(
            "Name the output objects",
            "NucleiBox",
            doc="Enter a name for the resulting objects.",
        )

        self.operation = Choice(
            "Select the method",
            O_ALL,
            doc="""\
Choose how to you want to handle overlapping boxes:

-  *{O_ASSIGN_ARBITRARY}:* Assign the overlapping region to the first box that gets those pixels.
-  *{O_ALLOW_OVERLAP}:* Save each object as a complete box even if two boxes overlap.
-  *{O_FIX_OVERLAP}:* Expand each box pixel by pixel until two boxes intersect
and then set those shapes as the box objects.
""".format(
                **{
                    "O_ASSIGN_ARBITRARY":O_ASSIGN_ARBITRARY,
                    "O_ALLOW_OVERLAP": O_ALLOW_OVERLAP,
                    "O_FIX_OVERLAP": O_FIX_OVERLAP,
                }
            ),
        )


    def settings(self):
        return [
            self.object_name,
            self.output_object_name,
            self.operation
        ]

    def visible_settings(self):
        result = [self.object_name, self.output_object_name, self.operation]

        return result

    def run(self, workspace):
        input_objects = workspace.object_set.get_objects(self.object_name.value)
        
        output_objects = cellprofiler_core.object.Objects()

        # TODO
        m = workspace.measurements
        x_min, x_max, y_min, y_max = self.get_box_boundaries(input_objects, m)

        input_labels, input_indices = workspace.object_set.get_labels(self.object_name.value)

        if self.operation == O_ALLOW_OVERLAP:   
            box_objects = []

            for i, label in enumerate(input_labels):
                # Assuming objects is a list of 2D masks 
                box = label[y_min[i]:y_max[i], x_min[i]:x_max[i]]
                object_id = input_indices[i]
                single_object_mask = (box == object_id).astype(numpy.uint8)
                box_objects.append(single_object_mask)

            output_objects.set_labels(box_objects, input_indices)

        elif self.operation == O_ASSIGN_ARBITRARY:
            box_objects = []
            output_label = numpy.zeros_like(input_labels[0], dtype=numpy.int32)

            for i, label in enumerate(input_labels):
                # Assuming objects is a list of 2D masks 
                box = label[y_min[i]:y_max[i], x_min[i]:x_max[i]]
                mask = box > 0 
                region = output_label[y_min[i]:y_max[i], x_min[i]:x_max[i]] # grab the box in the image
                region_mask = (mask) & (region == 0) # get a mask of the box where the pixels are free
                object_id = input_indices[i]
                region[region_mask] = object_id # set it as a label 
                output_label[y_min[i]:y_max[i], x_min[i]:x_max[i]] = region # save this object into the image 
                box_objects.append(region)

            output_objects.set_labels(output_label, input_indices)

        elif self.operation == O_FIX_OVERLAP:
            output_label = numpy.zeros_like(input_labels[0], dtype=numpy.int32)
            for i, label in enumerate(input_labels):
                # Assuming objects is a list of 2D masks 
                box = label[y_min[i]:y_max[i], x_min[i]:x_max[i]]
                region = output_label[y_min[i]:y_max[i], x_min[i]:x_max[i]] # grab the box in the image
                existing_labels = numpy.unique(region)
                existing_labels = existing_labels[existing_labels > 0]
                if len(existing_labels) > 0:
                    labels = self.watershed_resolve(box,region)
                    region_mask = labels == 1
                    existing_labels = labels == 2
                    object_id = input_indices[i]
                    region[region_mask] = object_id # set it as a label 
                else:
                    object_id = input_indices[i]
                    region[box] = object_id # set it as a label 
                output_label[y_min[i]:y_max[i], x_min[i]:x_max[i]] = region
            output_objects.set_labels(output_label, input_indices)    

        workspace.object_set.add_objects(output_objects, self.output_object_name.value)

        add_object_count_measurements(
            workspace.measurements,
            self.output_object_name.value,
            numpy.max(output_objects.segmented),
        )

        add_object_location_measurements(
            workspace.measurements,
            self.output_object_name.value,
            output_objects.segmented,
        )

        if self.show_window:
            workspace.display_data.input_objects_segmented = input_objects.segmented

            workspace.display_data.output_objects_segmented = output_objects.segmented

    def display(self, workspace, figure):
        input_objects_segmented = workspace.display_data.input_objects_segmented

        output_objects_segmented = workspace.display_data.output_objects_segmented

        figure.set_subplots((2, 1))
        cmap = figure.return_cmap(numpy.max(input_objects_segmented))

        figure.subplot_imshow_labels(
            0, 0, input_objects_segmented, self.object_name.value, colormap=cmap,
        )

        figure.subplot_imshow_labels(
            1,
            0,
            output_objects_segmented,
            self.output_object_name.value,
            sharexy=figure.subplot(0, 0),
            colormap=cmap,
        )

    def get_box_boundaries(self, object_name, m):
        """"Retreive the boundary box coordinates for all four sides"""
        x_min = m.get_current_measurement(object_name, ObjectSizeShapeFeatures.F_MIN_X.value)
        x_max = m.get_current_measurement(object_name, ObjectSizeShapeFeatures.F_MAX_X.value)
        y_min = m.get_current_measurement(object_name, ObjectSizeShapeFeatures.F_MIN_Y.value)
        y_max = m.get_current_measurement(object_name, ObjectSizeShapeFeatures.F_MAX_Y.value)
        return x_min, x_max, y_min, y_max
    
    def watershed_resolve(self, box1, box2):
        image = numpy.logical_or(box1, box2)
        distance = scipy.ndimage.distance_transform_edt(image)
        coords = skimage.feature.peak_local_max(distance, footprint=numpy.ones((3, 3)), labels=image)
        mask = numpy.zeros(distance.shape, dtype=bool)
        mask[tuple(coords.T)] = True
        markers, _ = scipy.ndimage.label(mask)
        labels = skimage.segmentation.watershed(-distance, markers, mask=image)
        return labels 



