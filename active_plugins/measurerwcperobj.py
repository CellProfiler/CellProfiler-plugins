#################################
#
# Imports from useful Python libraries
#
#################################

import numpy
import scipy.ndimage
import scipy.stats
from scipy.linalg import lstsq
import logging

#################################
#
# Imports from CellProfiler
#
##################################
from cellprofiler_core.constants.measurement import COLTYPE_FLOAT
from cellprofiler_core.module import Module
from cellprofiler_core.setting import Divider, Binary, ValidationError
from cellprofiler_core.setting.choice import Choice
from cellprofiler_core.setting.subscriber import (
    LabelSubscriber,
    LabelListSubscriber,
    ImageListSubscriber,
)
from cellprofiler_core.setting.text import Float
from cellprofiler_core.utilities.core.object import size_similarly
from centrosome.cpmorphology import fixup_scipy_ndimage_result as fix
from cellprofiler_core.utilities.core.object import crop_labels_and_image #NOT USED!
import cellprofiler_core.measurement

LOGGER = logging.getLogger(__name__)

__doc__ = """\
MeasureRWCperObj
===================

Measure Rank Weighed Colocalization (RWC) where both the pixel ranking and threshold are calculated per-object. 

**Rank Weighted Colocalization coefficient**: The RWC coefficient for a pair of images R and G is measured as **RWC1** = sum(Ri_coloc*Wi)/sum(Ri) and **RWC2** = sum(Gi_coloc*Wi)/sum(Gi), where Wi is Weight defined as Wi = (Rmax - Di)/Rmax where Rmax is the maximum of Ranks among R and G based on the max intensity, and Di = abs(Rank(Ri) - Rank(Gi)) (absolute difference in ranks between R and G) and Ri_coloc = Ri when Gi > 0, 0 otherwise and Gi_coloc = Gi when Ri >0, 0 otherwise. *(Singan et al. 2011, BMC Bioinformatics 12:407).*

Like regular RWC (measured using the MeasureColocalization module) RWCperObj calculates colocalization only in the intersection of the foreground (above-threshold pixels) of both images:

- For pixel intensity ranking: each of the object's pixels are assigned a rank according to their relative value within the object, with rank 1 being assigned to the dimmest pixel, and rank [n] (where [n] is the object's area in pixels) to the highest intensity pixel of the object.

- For threshold: threshold is calculated as a percentage of the highest pixel intensity within each object in each image.

Measurements made by this module
=================================
For each object:
  - RWCperObj_img1_img2: RWC1 with per-object pixel ranking and threshold calculation
  - RWCperObj_img2_img1: RWC2 with per-object pixel ranking and threshold calculation
  - RWCperObj_img1_img2_aboveThreshPixels_abs: the absolute area (in pixel units) of the intersection of the foreground (above-threshold pixels) of both images.
  - RWCperObj_img1_img2_aboveThreshPixels_rel: the relative area (compared to the total area of the object) of the intersection of the foreground (above-threshold pixels) of both images.

"""

"""This is the measurement template category"""
M_PER_OBJECT = "Within each object individually"

"""Feature name format for the RWCperObj measurement"""
F_RWCperObj_FORMAT = "Correlation_RWCperObj_%s_%s"


class MeasureRWCperObj(Module):
    module_name = "MeasureRWCperObj"
    category = "Measurement"
    variable_revision_number = 1

    def create_settings(self):
        """Create the initial settings for the module"""

        self.images_list = ImageListSubscriber(
            "Select images to measure",
            [],
            doc="""Select images to measure the correlation/colocalization in.""",
        )

        self.input_object_name = LabelSubscriber(
            text="Input object name",
            doc="These are the objects that the module operates on.",
        )

        self.objects_list = LabelListSubscriber(
            "Select objects to measure",
            [],
            doc="""\
Select the object to be measured.""",
        )

        self.thr = Float(
            "Set threshold as percentage of maximum intensity for each object",
            15,
            minval=0,
            maxval=99,
            doc="""\
You may choose to measure colocalization metrics only for those pixels above 
a certain threshold. Select the threshold as a percentage of the maximum intensity 
of each object [0-99].
If you want to measure in the whole object, set the threshold to 0.

""",
        )

        self.do_rwc = Binary(
            "Calculate the Rank Weighted Colocalization coefficients per object?",
            True,
            doc="""\
Select *{YES}* to run the Rank Weighted Colocalization coefficients per object.
""".format(
                **{"YES": "Yes"}
            ),
        )

        self.spacer = Divider(line=True)

    def settings(self):
        """Return the settings to be saved in the pipeline"""
        result = [
            self.images_list,
            self.thr,
            self.objects_list,
            self.do_rwc,
        ]
        return result
    
    def visible_settings(self):
        result = [
            self.images_list,
            self.objects_list,
            self.spacer,
            self.thr,
        ]
        return result

    def help_settings(self):
        """Return the settings to be displayed in the help menu"""
        help_settings = [
            self.thr,
            self.images_list,
            self.objects_list,
        ]
        return help_settings
    
    def get_image_pairs(self):
        """Yield all permutations of pairs of images to measure on.

        Yields the pairs of images in a canonical order.
        """
        for i in range(len(self.images_list.value) - 1):
            for j in range(i + 1, len(self.images_list.value)):
                yield (
                    self.images_list.value[i],
                    self.images_list.value[j],
                )
    

    def run(self, workspace):
        """Calculate measurements on an image set"""
        col_labels = ["First image", "Second image", "Objects", "Measurement", "Value"]
        statistics = []
        if len(self.images_list.value) < 2:
            raise ValueError("At least 2 images must be selected for analysis.")
        for first_image_name, second_image_name in self.get_image_pairs():
            for object_name in self.objects_list.value:
                statistics += self.run_image_pair_objects(
                    workspace, first_image_name, second_image_name, object_name
                )
        if self.show_window:
            workspace.display_data.statistics = statistics
            workspace.display_data.col_labels = col_labels

    def display(self, workspace, figure):
        statistics = workspace.display_data.statistics
        helptext = "default"
        figure.set_subplots((1, 1))
        figure.subplot_table(
            0, 0, statistics, workspace.display_data.col_labels, title=helptext
        )
    
    def run_image_pair_objects(
        self, workspace, first_image_name, second_image_name, object_name
    ):
        """Calculate per-object RWC between two images"""
        first_image = workspace.image_set.get_image(
            first_image_name, must_be_grayscale=True
        )
        second_image = workspace.image_set.get_image(
            second_image_name, must_be_grayscale=True
        )
        objects = workspace.object_set.get_objects(object_name)
        #
        # Crop both images to the size of the labels matrix
        #
        labels = objects.segmented
        try:
            first_pixels = objects.crop_image_similarly(first_image.pixel_data)
            first_mask = objects.crop_image_similarly(first_image.mask)
        except ValueError:
            first_pixels, m1 = size_similarly(labels, first_image.pixel_data)
            first_mask, m1 = size_similarly(labels, first_image.mask)
            first_mask[~m1] = False
        try:
            second_pixels = objects.crop_image_similarly(second_image.pixel_data)
            second_mask = objects.crop_image_similarly(second_image.mask)
        except ValueError:
            second_pixels, m1 = size_similarly(labels, second_image.pixel_data)
            second_mask, m1 = size_similarly(labels, second_image.mask)
            second_mask[~m1] = False
        mask = (labels > 0) & first_mask & second_mask
        first_pixels = first_pixels[mask]
        second_pixels = second_pixels[mask]
        labels = labels[mask]
        result = []
        first_pixel_data = first_image.pixel_data
        first_mask = first_image.mask
        first_pixel_count = numpy.product(first_pixel_data.shape)
        second_pixel_data = second_image.pixel_data
        second_mask = second_image.mask
        second_pixel_count = numpy.product(second_pixel_data.shape)
        #
        # Crop the larger image similarly to the smaller one
        #
        if first_pixel_count < second_pixel_count:
            second_pixel_data = first_image.crop_image_similarly(second_pixel_data)
            second_mask = first_image.crop_image_similarly(second_mask)
        elif second_pixel_count < first_pixel_count:
            first_pixel_data = second_image.crop_image_similarly(first_pixel_data)
            first_mask = second_image.crop_image_similarly(first_mask)
        mask = (
            first_mask
            & second_mask
            & (~numpy.isnan(first_pixel_data))
            & (~numpy.isnan(second_pixel_data))
        )
        if numpy.any(mask):
            fi = first_pixel_data[mask]
            si = second_pixel_data[mask]

        n_objects = objects.count
        # Handle case when both images for the correlation are completely masked out
       
        # Threshold as percentage of maximum intensity in each channel
        # Global threshold for all objects
        thr_fi = self.thr.value * numpy.max(fi) / 100
        thr_si = self.thr.value * numpy.max(si) / 100

        # Handle cases where there are no objects
        if n_objects == 0:
            RWC1_perObj = numpy.zeros((0,))
            RWC2_perObj = numpy.zeros((0,))
        elif numpy.where(mask)[0].__len__() == 0:
            corr = numpy.zeros((n_objects,))
            corr[:] = numpy.NaN
            RWC1_perObj = RWC2_perObj = corr

        else:
            lrange = numpy.arange(n_objects, dtype=numpy.int32) + 1  # +1 bc Objects start at index 0

            RWC1_perObj = numpy.zeros(len(lrange))
            RWC2_perObj = numpy.zeros(len(lrange))
            above_thresh_pixels_perObj = numpy.zeros(len(lrange))
            relative_above_thresh_pixels_perObj = numpy.zeros(len(lrange))

            # List of thresholds for each object (as percentage of maximum intensity of objects in each channel
            # Single threshold per object (it is calculated based on the highest pixel intensity in each object)
            tff_perObj = (self.thr.value / 100) * fix(
                scipy.ndimage.maximum(first_pixels, labels, lrange)
            )
            tss_perObj = (self.thr.value / 100) * fix(
                scipy.ndimage.maximum(second_pixels, labels, lrange)
            )


            for label in lrange: 

                first_pixels_perObj = first_pixels[labels==label]
                second_pixels_perObj = second_pixels[labels==label]

                # combined_thresh_perObj is a boolean array representing all the pixels in a single object
                # It is True in any pixel where BOTH first_pixels_perObj and second_pixels_perObj are above their respective threshold
                combined_thresh_perObj = (first_pixels_perObj > tff_perObj[label-1]) & (second_pixels_perObj > tss_perObj[label-1])
                
                # Count the number of above-threshold pixels remaining in the object, and get relative value to the size of the object
                # Store values in arrays (remember label starts at 1 and array index at 0)
                above_thresh_pixels_perObj[label-1] = numpy.count_nonzero(combined_thresh_perObj)
                relative_above_thresh_pixels_perObj[label-1] = above_thresh_pixels_perObj[label-1] / len(first_pixels_perObj)

                # sum of the above-threshold (for both channels) pixel intensities per object
                tot_fi_thr_perObj = scipy.ndimage.sum(
                    first_pixels_perObj[first_pixels_perObj > tff_perObj[label - 1]]
                )
                tot_si_thr_perObj = scipy.ndimage.sum(
                    second_pixels_perObj[second_pixels_perObj > tss_perObj[label - 1]]
                )

                # Array of pixel values above threshold for the object
                fi_thresh_obj = first_pixels_perObj[combined_thresh_perObj] 
                si_thresh_obj = second_pixels_perObj[combined_thresh_perObj] 
                
                # Array with a value assigned to each position according to ascending rank (0 is the rank of the lowest value)
                Rank1_perObj = numpy.lexsort([first_pixels_perObj]) 
                Rank2_perObj = numpy.lexsort([second_pixels_perObj])

                # This is a boolean array that has False every time pixel i from first_pixels (the list of pixel values from all objects in order) is equal to pixel i+1
                Rank1_U_perObj = numpy.hstack(
                    [[False], first_pixels_perObj[Rank1_perObj[:-1]] != first_pixels_perObj[Rank1_perObj[1:]]]
                ) 
                Rank2_U_perObj = numpy.hstack(
                    [[False], second_pixels_perObj[Rank2_perObj[:-1]] != second_pixels_perObj[Rank2_perObj[1:]]]
                )

                Rank1_S_perObj = numpy.cumsum(Rank1_U_perObj) 
                Rank2_S_perObj = numpy.cumsum(Rank2_U_perObj)

                Rank_im1_perObj = numpy.zeros(first_pixels_perObj.shape, dtype=int)
                Rank_im2_perObj = numpy.zeros(second_pixels_perObj.shape, dtype=int)

                Rank_im1_perObj[Rank1_perObj] = Rank1_S_perObj
                Rank_im2_perObj[Rank2_perObj] = Rank2_S_perObj

                R_perObj = max(Rank_im1_perObj.max(), Rank_im2_perObj.max()) + 1 #max rank among all ranks in both images (+1 to avoid division by 0)
                Di_perObj = abs(Rank_im1_perObj - Rank_im2_perObj) #absolute difference of rank between images in each pixel
                
                weight_perObj = (R_perObj - Di_perObj) * 1.0 / R_perObj
                weight_thresh_perObj = weight_perObj[combined_thresh_perObj]

                # Calculate RWCperObj only if any of the object pixels are above threshold
                if numpy.any(combined_thresh_perObj):
                    # RWC1_perObj and RWC2_perObj are arrays with the RWC value for each object in the set
                    RWC1_perObj[label-1] = numpy.array(
                        scipy.ndimage.sum(
                            fi_thresh_obj * weight_thresh_perObj
                        )
                    ) / numpy.array(tot_fi_thr_perObj)
                    RWC2_perObj[label-1] = numpy.array(
                        scipy.ndimage.sum(
                            si_thresh_obj * weight_thresh_perObj
                        )
                    ) / numpy.array(tot_si_thr_perObj)

            result += [
                [
                    first_image_name,
                    second_image_name,
                    object_name,
                    "Mean RWCperObj coeff",
                    "%.3f" % numpy.mean(RWC1_perObj),
                ],
                [
                    first_image_name,
                    second_image_name,
                    object_name,
                    "Median RWCperObj coeff",
                    "%.3f" % numpy.median(RWC1_perObj),
                ],
                [
                    first_image_name,
                    second_image_name,
                    object_name,
                    "Min RWCperObj coeff",
                    "%.3f" % numpy.min(RWC1_perObj),
                ],
                [
                    first_image_name,
                    second_image_name,
                    object_name,
                    "Max RWCperObj coeff",
                    "%.3f" % numpy.max(RWC1_perObj),
                ],
            ]
            result += [
                [
                    second_image_name,
                    first_image_name,
                    object_name,
                    "Mean RWCperObj coeff",
                    "%.3f" % numpy.mean(RWC2_perObj),
                ],
                [
                    second_image_name,
                    first_image_name,
                    object_name,
                    "Median RWCperObj coeff",
                    "%.3f" % numpy.median(RWC2_perObj),
                ],
                [
                    second_image_name,
                    first_image_name,
                    object_name,
                    "Min RWCperObj coeff",
                    "%.3f" % numpy.min(RWC2_perObj),
                ],
                [
                    second_image_name,
                    first_image_name,
                    object_name,
                    "Max RWCperObj coeff",
                    "%.3f" % numpy.max(RWC2_perObj),
                ],
            ]
            result += [
                [
                    first_image_name,
                    second_image_name,
                    object_name,
                    "Mean relative above-thresh px",
                    "%.3f" % numpy.mean(relative_above_thresh_pixels_perObj),
                ],
                [
                    first_image_name,
                    second_image_name,
                    object_name,
                    "Median relative above-thresh px",
                    "%.3f" % numpy.median(relative_above_thresh_pixels_perObj),
                ],
                [
                    first_image_name,
                    second_image_name,
                    object_name,
                    "Min relative above-thresh px",
                    "%.3f" % numpy.min(relative_above_thresh_pixels_perObj),
                ],
                [
                    first_image_name,
                    second_image_name,
                    object_name,
                    "Max relative above-thresh px",
                    "%.3f" % numpy.max(relative_above_thresh_pixels_perObj),
                ],
            ]

        rwc_measurement_1 = F_RWCperObj_FORMAT % (first_image_name, second_image_name)
        rwc_measurement_2 = F_RWCperObj_FORMAT % (second_image_name, first_image_name)
        rwc_measurement_3 = F_RWCperObj_FORMAT % (first_image_name, second_image_name) + "_aboveThreshPixels_abs"
        rwc_measurement_4 = F_RWCperObj_FORMAT % (first_image_name, second_image_name) + "_aboveThreshPixels_rel"


        workspace.measurements.add_measurement(object_name, rwc_measurement_1, RWC1_perObj)
        workspace.measurements.add_measurement(object_name, rwc_measurement_2, RWC2_perObj)
        workspace.measurements.add_measurement(object_name, rwc_measurement_3, above_thresh_pixels_perObj)
        workspace.measurements.add_measurement(object_name, rwc_measurement_4, relative_above_thresh_pixels_perObj)

        if n_objects == 0:
            return [
                [
                    first_image_name,
                    second_image_name,
                    object_name,
                    "Mean RWCperObj coeff",
                    "-",
                ],
                [
                    first_image_name,
                    second_image_name,
                    object_name,
                    "Median RWCperObj coeff",
                    "-",
                ],
                [
                    first_image_name,
                    second_image_name,
                    object_name,
                    "Min RWCperObj coeff",
                    "-",
                ],
                [
                    first_image_name,
                    second_image_name,
                    object_name,
                    "Max RWCperObj coeff",
                    "-",
                ],
            ]
        else:
            return result
        
    def get_measurement_columns(self, pipeline):
        """Return column definitions for all measurements made by this module"""
        columns = []
        for first_image, second_image in self.get_image_pairs():
            for i in range(len(self.objects_list.value)):
                object_name = self.objects_list.value[i]
                if self.do_rwc:
                    columns += [
                        (
                            object_name,
                            F_RWCperObj_FORMAT % (first_image, second_image),
                            COLTYPE_FLOAT,
                        ),
                        (
                            object_name,
                            F_RWCperObj_FORMAT % (second_image, first_image),
                            COLTYPE_FLOAT,
                        ),
                        (
                            object_name,
                            F_RWCperObj_FORMAT % (first_image, second_image) + "_aboveThreshPixels_abs",
                            COLTYPE_FLOAT,
                        ),
                        (
                            object_name,
                            F_RWCperObj_FORMAT % (first_image, second_image) + "_aboveThreshPixels_rel",
                            COLTYPE_FLOAT,
                        ),
                    ]
        return columns

    def get_categories(self, pipeline, object_name):
        """Return the categories supported by this module for the given object

        object_name - name of the measured object or IMAGE
        """
        return ["Correlation"]

    def get_measurements(self, pipeline, object_name, category):
        if self.get_categories(pipeline, object_name) == [category]:
            results = []
            results += ["RWCperObj"]
            return results
        return []

    def get_measurement_images(self, pipeline, object_name, category, measurement):
        """Return the joined pairs of images measured"""
        result = []
        if measurement in self.get_measurements(pipeline, object_name, category):
            for i1, i2 in self.get_image_pairs():
                result.append("%s_%s" % (i1, i2))
                result.append("%s_%s" % (i2, i1))
        return result

    def validate_module(self, pipeline):
        """Make sure chosen objects are selected only once"""
        if len(self.images_list.value) < 2:
            raise ValidationError("This module needs at least 2 images to be selected", self.images_list)

        if len(self.objects_list.value) == 0:
            raise ValidationError("No object sets selected", self.objects_list)

    def volumetric(self):
        return True


def get_scale(scale_1, scale_2):
    if scale_1 is not None and scale_2 is not None:
        return max(scale_1, scale_2)
    elif scale_1 is not None:
        return scale_1
    elif scale_2 is not None:
        return scale_2
    else:
        return 255
    

