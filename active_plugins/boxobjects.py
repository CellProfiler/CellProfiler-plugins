import cellprofiler_core.module as cpm
from cellprofiler_core.setting.choice import Choice
from cellprofiler_core.setting.subscriber import LabelSubscriber
from cellprofiler_core.setting.text import LabelName, Integer
from cellprofiler_core.utilities.core.module.identify import (
    add_object_location_measurements,
    add_object_count_measurements,
    get_object_measurement_columns,
)

from cellprofiler.modules import _help
from skimage.morphology import dilation, rectangle

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
import scipy.ndimage
from skimage.measure import regionprops, label
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
-  *{O_FIX_OVERLAP}:* Perform watershed operation to figure out the separation between both boxes. 
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
        input_label = input_objects.segmented
        bounding_boxes, input_indices = self.get_box_boundaries(input_label)
        label_to_bbox = dict(zip(input_indices, bounding_boxes))

        if self.operation == O_ALLOW_OVERLAP:   
            
            output_label = numpy.zeros_like(input_label, dtype=numpy.int32)
            for bbox, object_id in zip(bounding_boxes, input_indices):
                y_min, x_min, y_max, x_max = bbox
                output_label[y_min:y_max, x_min:x_max] = object_id

            output_objects.segmented = output_label 
            # output_objects.set_labels(box_objects, input_indices)

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
            # output_objects.set_labels(output_label, input_indices)

        elif self.operation == O_FIX_OVERLAP:
            
            
            output_label = numpy.zeros_like(input_label, dtype=numpy.int32)
            for bbox, object_id in zip(bounding_boxes, input_indices):
                
                y_min, x_min, y_max, x_max = bbox
                region = output_label[y_min:y_max, x_min:x_max] # grab the box in the image
                existing_ids = numpy.unique(region)
                existing_ids = existing_ids[existing_ids > 0]  # skip background
            
                if len(existing_ids) > 0:
                    updated_region = self.expand_box_simple(existing_ids, object_id, region)
                else:
                    updated_region = numpy.full(region.shape, object_id, dtype=numpy.int32)
    
                output_label[y_min:y_max, x_min:x_max] = updated_region
            output_objects.segmented = output_label 
           

            
            #     if len(existing_ids) > 0:
            #         existing_id = existing_ids[0]
            #         existing_mask = (output_label == existing_id).astype(numpy.uint8)
            #         new_mask = numpy.zeros_like(output_label, dtype=numpy.uint8)
            #         new_mask[y_min:y_max, x_min:x_max] = 2
            #         combined_mask = existing_mask + 2 * new_mask

            #         idx = input_indices.index(existing_id)  # if input_indices is a list
            #         existing_bbox = bounding_boxes[idx]

            #         labels = self.watershed_resolve(combined_mask, existing_bbox, bbox)
            #         # Set the output label with the new watershed boxes
            #         output_label[labels == 1] = existing_ids[0]
            #         output_label[labels == 2] = object_id
            #     else:
            #         region = numpy.full(region.shape, object_id, dtype=numpy.int32)
            #         output_label[y_min:y_max, x_min:x_max] = region

            # output_objects.segmented = output_label 
            # # output_objects.set_labels(output_label, input_indices)    

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

    def get_box_boundaries(self, input_label):
        """"Calculate the boundary box coordinates for all four sides"""
        props = regionprops(input_label)
        bounding_boxes = [prop.bbox for prop in props]
        input_indices = [prop.label for prop in props]
        return bounding_boxes, input_indices
    
    def watershed_resolve(self, combined_mask, existing_bbox, new_bbox):

        # existing_mask = (combined_mask & 1) > 0  
        # new_mask = (combined_mask & 2) > 0 
        mask = (combined_mask > 0)
        markers = numpy.zeros_like(combined_mask, dtype=numpy.int32)
        # markers[existing_mask] = 1
        # markers[new_mask] = 2

        # Compute centers
        existing_y_min, existing_x_min, existing_y_max, existing_x_max = box
        existing_center_y = (existing_y_min + existing_y_max) // 2
        existing_center_x = (existing_x_min + existing_x_max) // 2
        new_y_min, new_x_min, new_y_max, new_x_max = new_bbox
        new_center_y = (new_y_min + new_y_max) // 2
        new_center_x = (new_x_min + new_x_max) // 2

        # Set markers at those centers
        markers[existing_center_y, existing_center_x] = 1
        markers[new_center_y, new_center_x] = 2

        distance = scipy.ndimage.distance_transform_edt(mask)
        labels = skimage.segmentation.watershed( -distance, markers, mask=mask)
        return labels
    
    def expand_box(self, existing_bboxes, new_bbox,existing_ids, new_id, output_label):
 
        mask = numpy.zeros_like(output_label, dtype=bool)
        ids = []
        for box, id in zip(existing_bboxes, existing_ids):
            existing_y_min, existing_x_min, existing_y_max, existing_x_max = box
            existing_center_y = (existing_y_min + existing_y_max) // 2
            existing_center_x = (existing_x_min + existing_x_max) // 2
            
            mask[existing_center_y, existing_center_x] = True
            ids.append(id)

        new_y_min, new_x_min, new_y_max, new_x_max = new_bbox
        new_center_y = (new_y_min + new_y_max) // 2
        new_center_x = (new_x_min + new_x_max) // 2
        
        mask[new_center_y, new_center_x] = True
        ids.append(new_id)
        

        # for label in ids:
        #     seed = (output_label == id) & mask
        #     grown = dilation(seed, rectangle(3, 3))
        #     new_region = numpy.logical_and(grown, output_label == 0)
        #     if mask[new_region] == mask[region]:
        #         break
        #     else:
        #         mask[new_region] = True
        #         output_label[new_region] = label
        #     region = new_region.copy()


    def expand_box_simple(self, existing_ids, new_id, original_region):
        ids = list(existing_ids) + [new_id]

        # Blank canvas for the result
        region = numpy.zeros_like(original_region, dtype=numpy.int32)


        centroid_seeds = {}

        for id in ids:
            mask = (original_region == id)
            props = regionprops(mask.astype(numpy.uint8))
            if len(props) > 0:
                y, x = map(int, props[0].centroid)
                centroid_seeds[id] = (y, x)
            else:
                # Fallback: center of region if label not found
                height, width = original_region.shape
                centroid_seeds[id] = (height // 2, width // 2)

        max_iters = 100
        iter_count = 0
        changed = True

        while changed and iter_count < max_iters:
            changed = False
            for id in ids:
                cy, cx = centroid_seeds[id]
                seed = numpy.zeros_like(region, dtype=bool)
                seed[cy, cx] = True

                # Include already grown pixels for this label
                seed |= (region == id)

                grown = dilation(seed, rectangle(3, 3))
                new_region = grown & (region == 0)
                if numpy.any(new_region):
                    region[new_region] = id
                    changed = True
            iter_count += 1
        if iter_count == max_iters:
            print("Warning: max iterations reached in expand_box_simple")

        return region

        


