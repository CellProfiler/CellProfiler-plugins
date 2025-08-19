import cellprofiler_core.module as cpm
from cellprofiler_core.modules import loaddata
from cellprofiler_core.setting.choice import Choice
from cellprofiler_core.setting import Binary
from cellprofiler_core.setting.subscriber import LabelSubscriber
from cellprofiler_core.setting.text import Text
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

**BoxObjects** creates a new set of objects which are the bounding boxes of input objects.  It supports two methods for saving bounding box objects.

Since most measurement modules in CellProfiler do not currently support overlapping objects, the "Let the first box get the overlapping region" method 
assigns any overlapping object pixels to the first object. The next object is assigned only the free space. 

The "Crop each object from the image" method crops each object from the image and saves 
it as an individual image, thus enabling measurement of overlapping objects in a separate pipeline. Note that objects created by this method 
should not be used in downstream measurement modules in the same pipeline as they will cause an error.
The input objects can optionally be saved as cropped binary images that match the dimensions of the cropped raw image.
For each image set, BoxObjects creates a folder in the specified directory that can be named either after the raw image prefix or a custom user inputted name.
Additionally, it creates a load_data.csv file that contains the cropped images' URLs and metadata information.

See also **ExpandOrShrinkObjects** which creates larger objects from input objects, expanding or shrinking by a certain distance while maintaining 
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

-  *Count:* Number of bounding boxes objects in the images. 

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
O_USE_CROP = "Crop each object from the image"
SINGLE_NAME_TEXT = "Enter single site and well directory name"
FN_SINGLE_NAME = "Custom name"
FN_FROM_IMAGE = "From file prefix"
CREATE_MASKS_TEXT = "Do you want to save mask crops?"

library_mapping = {
    O_ASSIGN_ARBITRARY: 'assign_arbitrary',
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
            "Directory to save the folder",
            doc="Enter the directory where object crops and load_data.csv are saved.",
            value=DEFAULT_OUTPUT_FOLDER_NAME,
        )
        self.file_name_method = Choice(
            "Select method for constructing folder name",
            [FN_FROM_IMAGE, FN_SINGLE_NAME],
            FN_FROM_IMAGE,
            doc="""
            Select a method for constructing the folder name where cropped images and load_data.csv will be saved.

            -  *{FN_FROM_IMAGE}:* The folder will be constructed based on the original image filename.
            -  *{FN_SINGLE_NAME}:* A custom name will be given to the folder. You can use metadata tags to provide unique folder names per image set. Ensure that the metadata tags you use are sufficient to disambiguate between image sets.

            {USING_METADATA_TAGS_REF}
            """.format(
                **{
                    "FN_FROM_IMAGE": FN_FROM_IMAGE,
                    "FN_SINGLE_NAME": FN_SINGLE_NAME,
                    "USING_METADATA_TAGS_REF": _help.USING_METADATA_TAGS_REF,
                }
            ),
        )
        self.single_file_name = Text(
            SINGLE_NAME_TEXT,
            "Crop_Folder",
            metadata=True,
            doc="""
            Specify the folder name. You can use metadata tags to provide unique folder names per image set. 
            Ensure that the metadata tags you use are sufficient to disambiguate between image sets.
            {USING_METADATA_TAGS_REF}

            """.format(
                **{
                    "FN_SINGLE_NAME": FN_SINGLE_NAME,
                    "USING_METADATA_TAGS_REF": _help.USING_METADATA_TAGS_REF,
                }
            ),
        )

        self.create_masks = Binary(
            CREATE_MASKS_TEXT,
            True, 
            doc="Choose Yes to save original labeled objects as cropped images, No to skip."
        )

        self.operation = Choice(
            "Select the method",
            O_ALL,
            doc="""
            Choose how to you want to handle overlapping boxes:

            -  *{O_ASSIGN_ARBITRARY}:* Assign the overlapping region to the first box that gets those pixels.
            -  *{O_USE_CROP}:* Save cropped object from each image.

            """.format(
                **{
                    "O_ASSIGN_ARBITRARY":O_ASSIGN_ARBITRARY,
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
            self.directory, 
            self.file_name_method,
            self.single_file_name,
            self.create_masks
        ]

    def visible_settings(self):
        result = [self.object_name, self.output_object_name, self.operation]
        if self.operation in [O_USE_CROP]:
            result += [self.image_list, self.directory, self.file_name_method, self.create_masks]
            if self.file_name_method == FN_SINGLE_NAME:
               result += [self.single_file_name]
        return result

    def run(self, workspace):
        
        # Get the previously segmented objects 
        input_objects = workspace.object_set.get_objects(self.object_name.value)
        input_label = input_objects.segmented
        # Create new objects for the output
        output_objects = cellprofiler_core.object.Objects()
        # Calculate bounding boxes based on the segmented and labeled objects
        bounding_boxes, input_indices = self.get_box_boundaries(input_label)
        output_label = numpy.zeros_like(input_label, dtype=numpy.int32)

        ## Option does not work with any Measure modules -- depricated
        # if self.operation == O_ALLOW_OVERLAP:
        #     # We use ijv objects as the outputted objects to allow for overlap
        #     ijv_list = []

        #     for bbox, object_id in zip(bounding_boxes, input_indices):
        #         y_min, x_min, y_max, x_max = bbox
        #         height = y_max - y_min
        #         width = x_max - x_min

        #         # Get coordinates of the box area
        #         i_coords, j_coords = numpy.mgrid[0:height, 0:width]
        #         i_coords = i_coords + y_min
        #         j_coords = j_coords + x_min

        #         # Save in the format expected by ijv objects
        #         coords_flat = numpy.stack((i_coords.ravel(), j_coords.ravel()), axis=1)
        #         labels_flat = numpy.full((coords_flat.shape[0], 1), object_id, dtype=numpy.int32)

        #         ijv_box = numpy.hstack((coords_flat, labels_flat))
        #         ijv_list.append(ijv_box)

        #     # Combine all overlapping boxes into one IJV array
        #     ijv = numpy.vstack(ijv_list)
        #     output_objects.set_ijv(ijv)

        #     self.object_count = len(numpy.unique(ijv[:, 2]))
        #     # Create a segmentation image from the IJV array (only for displat)
        #     segmented = numpy.zeros(input_label.shape, dtype=numpy.int32)
        #     segmented[ijv[:, 0], ijv[:, 1]] = ijv[:, 2]
        #     self.object_location = ijv
        #     workspace.object_set.add_objects(output_objects, self.output_object_name.value)
            
        #     add_object_count_measurements(
        #         workspace.measurements,
        #         self.output_object_name.value,
        #         self.object_count,
        #     )

        #     add_object_location_measurements(
        #         workspace.measurements,
        #         self.output_object_name.value,
        #         self.object_location,
        #     )

        if self.operation == O_ASSIGN_ARBITRARY:
            box_objects = []

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

            
            # Save boxes as segmented objects 
            output_objects.segmented =  output_label 
            self.object_location = output_objects.segmented
            self.object_count = numpy.max(output_objects.segmented)
            workspace.object_set.add_objects(output_objects, self.output_object_name.value)


        elif self.operation == O_USE_CROP:
            
            # Get the user's directory
            directory = self.directory.get_absolute_path(workspace.measurements)
            all_rows = []
            box_objects = []

            # Extract metadata from the inputted load_data csv
            metadata_features, metadata_values, filename_values = self.extract_metadata(workspace)
            # Create CSV columns based on the inputted load_data csv
            csv_columns = self.create_csv_columns(metadata_features)

            # Make folder based on custom name or image prefix
            self.directory_name = self.get_folder_name(workspace, filename_values)
            save_directory = os.path.join(directory, self.directory_name)

            if not os.path.exists(save_directory):
                os.mkdir(save_directory)
            
            # Loop through each selected image
            for bbox, object_id in zip(bounding_boxes, input_indices):
                
                # region Crop Logic
                row = {col: "" for col in csv_columns}
                # Assign object ID and metadata
                row["Metadata_Crop_ID"] = object_id
                for feature_name, value in zip(metadata_features, metadata_values):
                    row[feature_name] = value

                # Raw image crop
                for image_name in self.image_list.value:
                    # Get the pixel data 
                    img = workspace.image_set.get_image(image_name)
                    image_data = img.pixel_data
                    y_min, x_min, y_max, x_max = bbox
                    cropped_image = image_data[y_min:y_max, x_min:x_max] 
                    image_save_filename = f"{image_name}_{self.output_object_name.value}_{object_id}.tiff"
                    image_full_path = os.path.join(save_directory, image_save_filename)

                    # Save cropped raw image
                    skimage.io.imsave(
                        image_full_path,
                        skimage.img_as_ubyte(cropped_image),
                        compression=(8,6),
                        check_contrast=False,
                    )
                    row[f"URL_{image_name}"] = image_full_path

                # Mask crop
                if self.create_masks.value:
                    # Create cropped mask image
                    segmented = numpy.zeros_like(image_data, dtype=numpy.int32)
                    segmented[y_min:y_max, x_min:x_max] = object_id

                    cropped_mask = input_label[y_min:y_max, x_min:x_max] == object_id
                    mask_save_filename = f"Object_{self.output_object_name.value}_{object_id}.tiff"
                    mask_full_path = os.path.join(save_directory, mask_save_filename)
                    skimage.io.imsave(
                        mask_full_path,
                        skimage.img_as_ubyte(cropped_mask),
                        compression=(8,6),
                        check_contrast=False,
                    )
                    row[f"URL_Object"] = mask_full_path

                all_rows.append(row)
                
                # endregion


                # region For visulization: create bounding boxes on the same image 
                # assigns the last object to the region
                # Extract coordinates of the sides for each bounding box 
                y_min, x_min, y_max, x_max = bbox
                mask = numpy.ones((y_max - y_min, x_max - x_min), dtype=bool)
                # Grab the box coordinates in the image
                region = output_label[y_min:y_max, x_min:x_max] 
                region_mask = mask
                region[region_mask] = object_id 
                # Save this object into our image array  
                output_label[y_min:y_max, x_min:x_max] = region 
                box_objects.append(region)
                # endregion

            
            # save load_data.csv
            save_path = os.path.join(save_directory, f"load_data_{self.output_object_name.value}.csv")
            with open(save_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=csv_columns)
                writer.writeheader()
                writer.writerows(all_rows)
                
            # Save each object individually based on inputted object (just for visualization)
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

    
    def get_folder_name(self, workspace, filename_values):
        """Get original folder name based on user input"""
        if self.file_name_method == FN_FROM_IMAGE:   
            name = [f for f in filename_values if f.endswith(".tiff")][0].split(".tiff")[0]
        elif self.file_name_method == FN_SINGLE_NAME:
            image_number = workspace.measurements.image_number
            # Get the text from the setting and replace any metadata placeholders
            name_template = self.single_file_name.value
            name = workspace.measurements.apply_metadata(name_template, image_number)
        return name
    
    def create_csv_columns(self, metadata_features):
        csv_columns = []

        for image_name in self.image_list.value:
            csv_columns.append(f"URL_{image_name}")
        if self.create_masks.value:
            csv_columns.append(f"URL_Object")

        csv_columns.append("Metadata_Crop_ID")
        csv_columns += metadata_features

        return csv_columns
    
    def extract_metadata(self, workspace):
        # Grab all feature names
        feature_names = workspace.measurements.get_feature_names("Image")
        # Grab metadata features
        metadata_features = [f for f in feature_names if f.startswith("Metadata_")]
        image_numbers = workspace.measurements.get_image_numbers()
        img_num = image_numbers[0]
        # Grab the image's metadata values
        metadata_values = [workspace.measurements.get_measurement("Image", feat, img_num) for feat in metadata_features]
        if self.file_name_method == FN_FROM_IMAGE:   
            filename_features = [f for f in feature_names if f.startswith("FileName_")]
            filename_values = [
                workspace.measurements.get_measurement("Image", feat, img_num)
                for feat in filename_features
            ]
        else: filename_values = []
        return metadata_features, metadata_values, filename_values
