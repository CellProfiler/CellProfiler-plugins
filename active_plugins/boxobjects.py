import cellprofiler_core.module as cpm
from cellprofiler_core.setting.choice import Choice
from cellprofiler_core.setting.subscriber import LabelSubscriber
from cellprofiler_core.setting.text import LabelName, Integer
from cellprofiler_core.utilities.core.module.identify import (
    add_object_location_measurements,
    add_object_count_measurements,
)

from cellprofiler.modules import _help

__doc__ = """\
BoxObjects
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
from skimage.measure import regionprops
import cellprofiler_core.object

O_ASSIGN_ARBITRARY = "Let the first box get the overlapping region"
O_ALLOW_OVERLAP = "Allow overlap between boxes"


library_mapping = {
    O_ASSIGN_ARBITRARY: 'assign_arbitrary',
    O_ALLOW_OVERLAP:'allow_overlap',  
}

O_ALL = list(library_mapping.keys())

class BoxObjects(cpm.Module):

    module_name = "BoxObjects"
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
            "BoundingBoxes",
            doc="Enter a name for the resulting objects.",
        )

        self.operation = Choice(
            "Select the method",
            O_ALL,
            doc="""\
Choose how to you want to handle overlapping boxes:

-  *{O_ASSIGN_ARBITRARY}:* Assign the overlapping region to the first box that gets those pixels.
-  *{O_ALLOW_OVERLAP}:* Save each object as a complete box even if two boxes overlap.
""".format(
                **{
                    "O_ASSIGN_ARBITRARY":O_ASSIGN_ARBITRARY,
                    "O_ALLOW_OVERLAP": O_ALLOW_OVERLAP,
                }
            ),
        )


    def settings(self):
        return [
            self.object_name,
            self.output_object_name,
            self.operation,
        ]

    def visible_settings(self):
        result = [self.object_name, self.output_object_name, self.operation]

        return result

    def run(self, workspace):
        input_objects = workspace.object_set.get_objects(self.object_name.value)
        output_objects = cellprofiler_core.object.Objects()

        input_label = input_objects.segmented
        bounding_boxes, input_indices = self.get_box_boundaries(input_label)

        if self.operation == O_ALLOW_OVERLAP:
            ijv_list = []

            for bbox, object_id in zip(bounding_boxes, input_indices):
                y_min, x_min, y_max, x_max = bbox
                height = y_max - y_min
                width = x_max - x_min

                # Get coordinates of the box area
                i_coords, j_coords = numpy.mgrid[0:height, 0:width]
                i_coords = i_coords + y_min
                j_coords = j_coords + x_min

                coords_flat = numpy.stack((i_coords.ravel(), j_coords.ravel()), axis=1)
                labels_flat = numpy.full((coords_flat.shape[0], 1), object_id, dtype=numpy.int32)

                ijv_box = numpy.hstack((coords_flat, labels_flat))
                ijv_list.append(ijv_box)

            # Combine all overlapping boxes into one IJV array
            ijv = numpy.vstack(ijv_list)

            output_objects.set_ijv(ijv)
            
            self.object_count = len(numpy.unique(ijv[:, 2]))
            # Create a segmentation image from the IJV array
            segmented = numpy.zeros(input_label.shape, dtype=numpy.int32)
            segmented[ijv[:, 0], ijv[:, 1]] = ijv[:, 2]

            # assign the full segmentation image to the output object
            output_objects.segmented = segmented

        elif self.operation == O_ASSIGN_ARBITRARY:
            box_objects = []
            output_label = numpy.zeros_like(input_label, dtype=numpy.int32)

            for bbox, object_id in zip(bounding_boxes, input_indices):
                
                y_min, x_min, y_max, x_max = bbox
                mask = numpy.ones((y_max - y_min, x_max - x_min), dtype=bool)
                region = output_label[y_min:y_max, x_min:x_max] # grab the box in the image
                region_mask = (mask) & (region == 0) # get a mask of the box where the pixels are free
                region[region_mask] = object_id # set it as a label 
                output_label[y_min:y_max, x_min:x_max] = region # save this object into the image 
                box_objects.append(region)

            output_objects.segmented = output_label 
            self.object_count = numpy.max(output_objects.segmented)
        
        add_object_count_measurements(
            workspace.measurements,
            self.output_object_name.value,
            self.object_count,
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

    def get_box_boundaries(self, input_label):
        """"Calculate the boundary box coordinates for all four sides"""
        props = regionprops(input_label)
        bounding_boxes = [prop.bbox for prop in props]
        input_indices = [prop.label for prop in props]
        return bounding_boxes, input_indices

    


        


