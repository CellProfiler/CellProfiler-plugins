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


"""

#
# Constants
#
# It's good programming practice to replace things like strings with
# constants if they will appear more than once in your program. That way,
# if someone wants to change the text, that text will change everywhere.
# Also, you can't misspell it by accident.
#

"""This is the measurement template category"""
C_MEASUREMENT_TEMPLATE = "MT"
M_PER_OBJECT = "Within each object individually"

"""Feature name format for the RWC Coefficient measurement"""
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
            "Set threshold as percentage of maximum intensity for the images",
            15,
            minval=0,
            maxval=99,
            doc="""\
You may choose to measure colocalization metrics only for those pixels above 
a certain threshold. Select the threshold as a percentage of the maximum intensity 
of the above image [0-99].

This value is used by the Overlap, Manders, and Rank Weighted Colocalization 
measurements.
""",
        )

        self.do_rwc = Binary(
            "Calculate the Rank Weighted Colocalization coefficients?",
            True,
            doc="""\
Select *{YES}* to run the Rank Weighted Colocalization coefficients.
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
            # self.images_or_objects,
            self.objects_list,
            # self.do_all,
            # self.do_corr_and_slope,
            # self.do_manders,
            self.do_rwc,
            # self.do_overlap,
            # self.do_costes,
            # self.fast_costes,
        ]
        return result
    
    def visible_settings(self):
        result = [
            self.images_list,
            self.objects_list,
            self.spacer,
            self.thr,
            # self.do_rwc,
            # self.images_or_objects,
        ]
        return result

    def help_settings(self):
        """Return the settings to be displayed in the help menu"""
        help_settings = [
            # self.images_or_objects,
            self.thr,
            self.images_list,
            self.objects_list,
            # self.do_all,
            # self.fast_costes,
        ]
        return help_settings
    
    def get_image_pairs(self):
        """Yield all permutations of pairs of images to correlate

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
        """Calculate per-object correlations between intensities in two images"""
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

        #fi_thresh = fi[combined_thresh] #array including ONLY the pixels from fi that are above threshold in both images
        #si_thresh = si[combined_thresh] #array including ONLY the pixels from si that are above threshold in both images
        #tot_fi_thr = fi[(fi > thr_fi)].sum() #single value of the integrated intensity of above-threshold pixels for fi (?)
        #tot_si_thr = si[(si > thr_si)].sum() #single value of the integrated intensity of above-threshold pixels for si (?)
       
        if n_objects == 0:
            # corr = numpy.zeros((0,))
            # overlap = numpy.zeros((0,))
            # K1 = numpy.zeros((0,))
            # K2 = numpy.zeros((0,))
            # M1 = numpy.zeros((0,))
            # M2 = numpy.zeros((0,))
            RWC1 = numpy.zeros((0,))
            RWC2 = numpy.zeros((0,))
            # C1 = numpy.zeros((0,))
            # C2 = numpy.zeros((0,))
        elif numpy.where(mask)[0].__len__() == 0:
            corr = numpy.zeros((n_objects,))
            corr[:] = numpy.NaN
            # overlap = K1 = K2 = M1 = M2 = RWC1 = RWC2 = C1 = C2 = corr
            RWC1 = RWC2 = corr

        else:
            lrange = numpy.arange(n_objects, dtype=numpy.int32) + 1

            # RWC Coefficient
            RWC1 = numpy.zeros(len(lrange))
            RWC2 = numpy.zeros(len(lrange))

            # Threshold as percentage of maximum intensity of objects in each channel
            # Single threshold per object (it is calculated based on the highest pixel intensity in each object)
            tff = (self.thr.value / 100) * fix(
                scipy.ndimage.maximum(first_pixels, labels, lrange)
            )
            tss = (self.thr.value / 100) * fix(
                scipy.ndimage.maximum(second_pixels, labels, lrange)
            )
            
            #NOT USED!
            tot_fi_thr = scipy.ndimage.sum(
                first_pixels[first_pixels >= tff[labels - 1]],
                labels[first_pixels >= tff[labels - 1]],
                lrange,
            )
            tot_si_thr = scipy.ndimage.sum(
                second_pixels[second_pixels >= tss[labels - 1]],
                labels[second_pixels >= tss[labels - 1]],
                lrange,
            )

            for label in numpy.unique(labels):
                # set first_pixels to only what's inside that label and rename --> obj_pixels_img1
                # same with second_pixels to only what's inside that label and rename --> obj_pixels_img2
                # same with labels to only what's inside that label and rename --> obj_label
                # same with lrange to only what's inside that label and rename --> obj_lrange
                # same with fi_thresh, si_thresh, combined_thresh, tot_fi_thr, tot_si_thr
                # - move the 770 block inside this function after subsettingfirst_pixels and second_pixels
                

                #ASK BETH - in this case where no object has disjointed pixels, the order of the values of first_pixels matches the order of the objects. What would happen with disjointed objects?!
                first_pixels_perObj = first_pixels[labels==label]
                second_pixels_perObj = second_pixels[labels==label]

                # Local threshold for each object individually
                thr_fi_perObj = self.thr.value * numpy.max(first_pixels_perObj) / 100
                thr_si_perObj = self.thr.value * numpy.max(second_pixels_perObj) / 100

                #combined_thersh is an boolean array representing all the pixels in a single object, that is True in any pixel where BOTH fi and si are above their respective threshold
                #is thr_fi == tff[labels==label] ??
                # combined_thresh_perObj = (first_pixels[labels==label] > tff[labels==label]) & (second_pixels[labels==label] > tss[labels==label])
                combined_thresh_perObj = (first_pixels_perObj > thr_fi_perObj) & (second_pixels_perObj > thr_si_perObj)

                # sum of the above-threshold (for both channels) pixel intensities per object
                tot_fi_thr_perObj = scipy.ndimage.sum(
                    first_pixels_perObj[first_pixels_perObj >= tff[label - 1]]
                )
                tot_si_thr_perObj = scipy.ndimage.sum(
                    second_pixels_perObj[second_pixels_perObj >= tff[label - 1]]
                )

                #array of pixel values above threshold for the object
                fi_thresh_obj = first_pixels_perObj[combined_thresh_perObj] 
                si_thresh_obj = second_pixels_perObj[combined_thresh_perObj] 
                
                #array with a value assigned to each position according to ascending rank (0 is the rank of the lowest value)
                Rank1_perObj = numpy.lexsort([first_pixels_perObj]) 
                Rank2_perObj = numpy.lexsort([second_pixels_perObj])

                #ASK BETH! this is a boolean array that has False every time pixel i from first_pixels (the list of pixel values from all objects in order) is equal to pixel i+1
                Rank1_U_perObj = numpy.hstack(
                    [[False], first_pixels_perObj[Rank1_perObj[:-1]] != first_pixels_perObj[Rank1_perObj[1:]]]
                ) 
                Rank2_U_perObj = numpy.hstack(
                    [[False], second_pixels_perObj[Rank2_perObj[:-1]] != second_pixels_perObj[Rank2_perObj[1:]]]
                )

                #ask BETH, array with cumulative number of 'True' 
                Rank1_S_perObj = numpy.cumsum(Rank1_U_perObj) 
                Rank2_S_perObj = numpy.cumsum(Rank2_U_perObj)

                Rank_im1_perObj = numpy.zeros(first_pixels_perObj.shape, dtype=int)
                Rank_im2_perObj = numpy.zeros(second_pixels_perObj.shape, dtype=int)

                Rank_im1_perObj[Rank1_perObj] = Rank1_S_perObj
                Rank_im2_perObj[Rank2_perObj] = Rank2_S_perObj

                R_perObj = max(Rank_im1_perObj.max(), Rank_im2_perObj.max()) + 1 #max rank among all ranks in both ch
                Di_perObj = abs(Rank_im1_perObj - Rank_im2_perObj) #absolute difference of rank between ch in each pixel
                
                weight_perObj = (R_perObj - Di_perObj) * 1.0 / R_perObj
                weight_thresh_perObj = weight_perObj[combined_thresh_perObj]

                # Calculate RWC only if any of the object pixels are above threshold
                # ...which will always be the case since the thr is calculated as a % of the max intensity pixel in each object
                # ...unless the above-threshold pixels on one channel don't match the ones on the other, so I guess it makes sense...
                if numpy.any(combined_thresh_perObj):
                    # RWC1 and 2 are arrays with the RWC value for each object in the set
                    RWC1[label-1] = numpy.array(
                        scipy.ndimage.sum(
                            fi_thresh_obj * weight_thresh_perObj
                        )
                    ) / numpy.array(tot_fi_thr_perObj)
                    RWC2[label-1] = numpy.array(
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
                    "%.3f" % numpy.mean(RWC1),
                ],
                [
                    first_image_name,
                    second_image_name,
                    object_name,
                    "Median RWCperObj coeff",
                    "%.3f" % numpy.median(RWC1),
                ],
                [
                    first_image_name,
                    second_image_name,
                    object_name,
                    "Min RWCperObj coeff",
                    "%.3f" % numpy.min(RWC1),
                ],
                [
                    first_image_name,
                    second_image_name,
                    object_name,
                    "Max RWCperObj coeff",
                    "%.3f" % numpy.max(RWC1),
                ],
            ]
            result += [
                [
                    second_image_name,
                    first_image_name,
                    object_name,
                    "Mean RWCperObj coeff",
                    "%.3f" % numpy.mean(RWC2),
                ],
                [
                    second_image_name,
                    first_image_name,
                    object_name,
                    "Median RWCperObj coeff",
                    "%.3f" % numpy.median(RWC2),
                ],
                [
                    second_image_name,
                    first_image_name,
                    object_name,
                    "Min RWCperObj coeff",
                    "%.3f" % numpy.min(RWC2),
                ],
                [
                    second_image_name,
                    first_image_name,
                    object_name,
                    "Max RWCperObj coeff",
                    "%.3f" % numpy.max(RWC2),
                ],
            ]

        rwc_measurement_1 = F_RWCperObj_FORMAT % (first_image_name, second_image_name)
        rwc_measurement_2 = F_RWCperObj_FORMAT % (second_image_name, first_image_name)
        workspace.measurements.add_measurement(object_name, rwc_measurement_1, RWC1)
        workspace.measurements.add_measurement(object_name, rwc_measurement_2, RWC2)

        if n_objects == 0:
            return [
                [
                    first_image_name,
                    second_image_name,
                    object_name,
                    "Mean correlation",
                    "-",
                ],
                [
                    first_image_name,
                    second_image_name,
                    object_name,
                    "Median correlation",
                    "-",
                ],
                [
                    first_image_name,
                    second_image_name,
                    object_name,
                    "Min correlation",
                    "-",
                ],
                [
                    first_image_name,
                    second_image_name,
                    object_name,
                    "Max correlation",
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
                # For asymmetric, return both orderings
                if measurement in ("K", "Manders", "RWC", "Costes"):
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
    

