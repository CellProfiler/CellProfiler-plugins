import cellprofiler_core.module as cpm
from cellprofiler_core.setting.choice import Choice
from cellprofiler_core.setting.subscriber import LabelSubscriber
from cellprofiler_core.setting.subscriber import ImageListSubscriber
from cellprofiler_core.setting.text import LabelName, Integer
from cellprofiler_core.utilities.core.module.identify import (
    add_object_location_measurements,
    add_object_count_measurements,
)
from cellprofiler.modules import _help
from cellprofiler_core.setting.text import Directory
from cellprofiler_core.preferences import DEFAULT_OUTPUT_FOLDER_NAME

__doc__ = """\
BoxObjects
=====================

**BoxObjects** creates objects which are bounding boxes around pre-defined objects. 

The module calculate the bounding box around each inputted object. 
You can specify if you want the objects to overlap and be defined as ijv objects, 
or if you do not want the objects to overlab and instead be defined as 
segmented objects. In the case where you do not want the objects to overlap, 
the pixels in the overlap region will be assigned to the object that first claims 
them during assignment. 

See also **ExpandorShrinkObjects** which creates larger objects from the segmented 
objects, it expands of shring these objects by a certain distance while maintaining 
the object's shape. 


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

-  *Count:* Number ofbounding boxe objects in the image.

**Object measurements:**

-  *Location\_X, Location\_Y:* Pixel (*X,Y*) coordinates of each bounding box.
""".format(
    **{"HELP_ON_SAVING_OBJECTS": _help.HELP_ON_SAVING_OBJECTS}
)

import centrosome.cpmorphology
import numpy
from skimage.measure import regionprops
import skimage 
import cellprofiler_core.object
import os
import csv

O_ASSIGN_ARBITRARY = "Let the first box get the overlapping region"
O_ALLOW_OVERLAP = "Allow overlap between boxes"
O_USE_CROP = "Crop each object from the image"


library_mapping = {
    O_ASSIGN_ARBITRARY: 'assign_arbitrary',
    O_ALLOW_OVERLAP:'allow_overlap',  
    O_USE_CROP: "use_crop",
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
        self.image_list = ImageListSubscriber(
            "Select the image(s) to crop", 
            doc="Select the image to crop",
        )
        self.directory = Directory(
            "Directory",
            doc="Enter the directory where object crops are saved.",
            value=DEFAULT_OUTPUT_FOLDER_NAME,
        )
        self.operation = Choice(
            "Select the method",
            O_ALL,
            doc="""\
        
Choose how to you want to handle overlapping boxes:

-  *{O_ASSIGN_ARBITRARY}:* Assign the overlapping region to the first box that gets those pixels.
-  *{O_ALLOW_OVERLAP}:* Save each object as a complete box even if two boxes overlap.
-  *{O_USE_CROP}:* Save cropped object from each image.

""".format(
                **{
                    "O_ASSIGN_ARBITRARY":O_ASSIGN_ARBITRARY,
                    "O_ALLOW_OVERLAP": O_ALLOW_OVERLAP,
                    "O_USE_CROP": O_USE_CROP,
                }
            ),
        )


    def settings(self):
        return [
            self.object_name,
            self.output_object_name,
            self.operation,
            self.image_list, 
            self.directory
        ]

    def visible_settings(self):
        result = [self.object_name, self.output_object_name, self.operation]
        if self.operation in [O_USE_CROP]:
            result += [self.image_list, self.directory]
        return result

    def run(self, workspace):
        
        input_objects = workspace.object_set.get_objects(self.object_name.value)
        output_objects = cellprofiler_core.object.Objects()

        input_label = input_objects.segmented
        bounding_boxes, input_indices = self.get_box_boundaries(input_label)

        if self.operation == O_ALLOW_OVERLAP:
            # We use ijv objects as the outputted objects to allow for overlap
            ijv_list = []

            for bbox, object_id in zip(bounding_boxes, input_indices):
                y_min, x_min, y_max, x_max = bbox
                height = y_max - y_min
                width = x_max - x_min

                # Get coordinates of the box area
                i_coords, j_coords = numpy.mgrid[0:height, 0:width]
                i_coords = i_coords + y_min
                j_coords = j_coords + x_min

                # Save in the format expected by ijv objects
                coords_flat = numpy.stack((i_coords.ravel(), j_coords.ravel()), axis=1)
                labels_flat = numpy.full((coords_flat.shape[0], 1), object_id, dtype=numpy.int32)

                ijv_box = numpy.hstack((coords_flat, labels_flat))
                ijv_list.append(ijv_box)

            # Combine all overlapping boxes into one IJV array
            ijv = numpy.vstack(ijv_list)
            output_objects.set_ijv(ijv)

            self.object_count = len(numpy.unique(ijv[:, 2]))
            # Create a segmentation image from the IJV array (only for displat)
            segmented = numpy.zeros(input_label.shape, dtype=numpy.int32)
            segmented[ijv[:, 0], ijv[:, 1]] = ijv[:, 2]
            self.object_location = ijv
            workspace.object_set.add_objects(output_objects, self.output_object_name.value)
            
            add_object_count_measurements(
                workspace.measurements,
                self.output_object_name.value,
                self.object_count,
            )

            add_object_location_measurements(
                workspace.measurements,
                self.output_object_name.value,
                self.object_location,
            )

        elif self.operation == O_ASSIGN_ARBITRARY:
            box_objects = []
            # Create array with the dimensions of the image 
            output_label = numpy.zeros_like(input_label, dtype=numpy.int32)

            for bbox, object_id in zip(bounding_boxes, input_indices):
                # Extract coordinates of the sides for each bounding box 
                y_min, x_min, y_max, x_max = bbox
                mask = numpy.ones((y_max - y_min, x_max - x_min), dtype=bool)
                # Grab the box coordinates in the image
                region = output_label[y_min:y_max, x_min:x_max] 
                # Get a mask of the box where the pixels are free
                region_mask = (mask) & (region == 0) 
                region[region_mask] = object_id 
                # Save this object into our image array  
                output_label[y_min:y_max, x_min:x_max] = region 
                box_objects.append(region)

            
            # Save boxes are segmented objects 
            output_objects.segmented =  output_label 
            self.object_location = output_objects.segmented
            self.object_count = numpy.max(output_objects.segmented)
            workspace.object_set.add_objects(output_objects, self.output_object_name.value)

            add_object_count_measurements(
                workspace.measurements,
                self.output_object_name.value,
                self.object_count,
            )

            add_object_location_measurements(
                workspace.measurements,
                self.output_object_name.value,
                self.object_location,
            )
        
        elif self.operation == O_USE_CROP:
            directory = self.directory.get_absolute_path(workspace.measurements)
            # Loop through each selected image
            load_data_rows = []
            header = None  # will store all feature names

            # Get all image-level features once
            feature_names = workspace.measurements.get_feature_names("Image")

            # Prepare CSV header only once
            header = feature_names

            for bbox, object_id in zip(bounding_boxes, input_indices):

                for image_name in self.image_list.value:
                    # Fetch the image data from the workspace
                    img = workspace.image_set.get_image(image_name)
                    # Get the pixel data as a NumPy array
                    image_data = img.pixel_data

                    y_min, x_min, y_max, x_max = bbox
                    cropped_image = image_data[y_min:y_max, x_min:x_max] 
                    label_save_filename = f"{image_name}_{self.output_object_name.value}_{object_id}.tiff"

                    full_path = os.path.join(directory, label_save_filename)
                    skimage.io.imsave(
                        full_path,
                        skimage.img_as_ubyte(cropped_image),
                        compression=(8,6),
                        check_contrast=False,
                    )

                    row = [workspace.measurements.get_current_image_measurement(feat)
                        for feat in header]

                    # Optionally update filename/path for this new crop
                    for i, feat in enumerate(header):
                        if feat.startswith(f"FileName_{image_name}"):
                            row[i] = label_save_filename
                        elif feat.startswith(f"PathName_{image_name}"):
                            row[i] = directory
                            load_data_rows.append(row)
                            
                mask = numpy.ones(cropped_image.shape[:2], dtype=bool)
                output_objects = cellprofiler_core.object.Objects()
                segmented = numpy.zeros_like(image_data, dtype=numpy.int32)
                segmented[y_min:y_max, x_min:x_max] = object_id
                output_objects.segmented = segmented
                # save each object individually
                object_name = f"{self.output_object_name.value}_object{object_id}"
                workspace.object_set.add_objects(output_objects, object_name)

                self.object_count = 1
                center_x = int((x_min + x_max) / 2.0)
                center_y = int((y_min + y_max) / 2.0)
                self.object_location = numpy.array([[center_y, center_x]])

                add_object_count_measurements(
                    workspace.measurements,
                    object_name,
                    self.object_count,
                )

                add_object_location_measurements(
                    workspace.measurements,
                    object_name,
                    self.object_location,
                )


            # Write the CSV after loop
            with open(os.path.join(directory, "LoadData_Cropped.csv"), "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(header)
                writer.writerows(load_data_rows)
            
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
        """"Calculate the boundary box coordinates for all four sides
        
        Parameters: 
            input_label (numpy.array) : internal representation of the image 
        
        Returns:
            bounding_boxes (list): coodinates of the bounding box sides
            input_indices (int): labels created by props method
        """
        props = regionprops(input_label)
        bounding_boxes = [prop.bbox for prop in props]
        input_indices = [prop.label for prop in props]
        return bounding_boxes, input_indices

    


        


