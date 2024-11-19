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
from cellprofiler_core.utilities.core.object import crop_labels_and_image

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
F_RWC_FORMAT = "Correlation_RWC_%s_%s"


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
        thr_fi = self.thr.value * numpy.max(fi) / 100
        thr_si = self.thr.value * numpy.max(si) / 100
        combined_thresh = (fi > thr_fi) & (si > thr_si) # CHECK THIS DEFINITION, IT HAS BEEN CHANGED FROM THE ORIGINAL BUT IDK IF IT'S OK!
        fi_thresh = fi[combined_thresh]
        si_thresh = si[combined_thresh]
        tot_fi_thr = fi[(fi > thr_fi)].sum()
        tot_si_thr = si[(si > thr_si)].sum()
       
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

            for label in numpy.unique(labels):
                # set first_pixels to only what's inside that label and rename --> obj_pixels_img1
                # same with second_pixels to only what's inside that label and rename --> obj_pixels_img2
                # same with labels to only what's inside that label and rename --> obj_label
                # same with lrange to only what's inside that label and rename --> obj_lrange
                # same with fi_thresh, si_thresh, combined_thresh, tot_fi_thr, tot_si_thr
                # - move the 770 block inside this function after subsettingfirst_pixels and second_pixels

                # objects.segmented is an array (10,10) were each pixel is assigned its corresponding label (1,2 or 3)

                #delete these and replace with Beth's suggestion
                obj_pixels_img1 = numpy.where(labels==label,first_pixel_data,0)
                obj_pixels_img2 = numpy.where(labels==label,second_pixel_data,0)
                
                obj_lrange = lrange[lrange==label]
                
                [Rank1] = numpy.lexsort(([obj_label], [obj_pixels_img1]))
                [Rank2] = numpy.lexsort(([obj_label], [obj_pixels_img2]))
                Rank1_U = numpy.hstack(
                    [[False], first_pixels[Rank1[:-1]] != first_pixels[Rank1[1:]]]
                )
                Rank2_U = numpy.hstack(
                    [[False], second_pixels[Rank2[:-1]] != second_pixels[Rank2[1:]]]
                )
                Rank1_S = numpy.cumsum(Rank1_U)
                Rank2_S = numpy.cumsum(Rank2_U)
                Rank_obj_im1 = numpy.zeros(obj_pixels_img1.shape, dtype=int)
                Rank_obj_im2 = numpy.zeros(obj_pixels_img2.shape, dtype=int)
                Rank_obj_im1[Rank1] = Rank1_S
                Rank_obj_im2[Rank2] = Rank2_S

                R = max(Rank_obj_im1.max(), Rank_obj_im2.max()) + 1
                Di = abs(Rank_obj_im1 - Rank_obj_im2)
                weight = (R - Di) * 1.0 / R
                weight_thresh = weight[combined_thresh]

                if numpy.any(combined_thresh):
                    RWC1 = numpy.array(
                        scipy.ndimage.sum(
                            fi_thresh * weight_thresh, labels[combined_thresh], lrange
                        )
                    ) / numpy.array(tot_fi_thr)
                    RWC2 = numpy.array(
                        scipy.ndimage.sum(
                            si_thresh * weight_thresh, labels[combined_thresh], lrange
                        )
                    ) / numpy.array(tot_si_thr)
                
                # Threshold as percentage of maximum intensity of objects in each channel
                tff = (self.thr.value / 100) * fix(
                    scipy.ndimage.maximum(first_pixels, labels, lrange)
                )
                tss = (self.thr.value / 100) * fix(
                    scipy.ndimage.maximum(second_pixels, labels, lrange)
                )

                combined_thresh = (first_pixels >= tff[labels - 1]) & (
                    second_pixels >= tss[labels - 1]
                )
                fi_thresh = first_pixels[combined_thresh]
                si_thresh = second_pixels[combined_thresh]
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
                ### update RWC1 and RWC2 with ther right position and the right values

            result += [
                [
                    first_image_name,
                    second_image_name,
                    object_name,
                    "Mean RWC coeff",
                    "%.3f" % numpy.mean(RWC1),
                ],
                [
                    first_image_name,
                    second_image_name,
                    object_name,
                    "Median RWC coeff",
                    "%.3f" % numpy.median(RWC1),
                ],
                [
                    first_image_name,
                    second_image_name,
                    object_name,
                    "Min RWC coeff",
                    "%.3f" % numpy.min(RWC1),
                ],
                [
                    first_image_name,
                    second_image_name,
                    object_name,
                    "Max RWC coeff",
                    "%.3f" % numpy.max(RWC1),
                ],
            ]
            result += [
                [
                    second_image_name,
                    first_image_name,
                    object_name,
                    "Mean RWC coeff",
                    "%.3f" % numpy.mean(RWC2),
                ],
                [
                    second_image_name,
                    first_image_name,
                    object_name,
                    "Median RWC coeff",
                    "%.3f" % numpy.median(RWC2),
                ],
                [
                    second_image_name,
                    first_image_name,
                    object_name,
                    "Min RWC coeff",
                    "%.3f" % numpy.min(RWC2),
                ],
                [
                    second_image_name,
                    first_image_name,
                    object_name,
                    "Max RWC coeff",
                    "%.3f" % numpy.max(RWC2),
                ],
            ]

        rwc_measurement_1 = F_RWC_FORMAT % (first_image_name, second_image_name)
        rwc_measurement_2 = F_RWC_FORMAT % (second_image_name, first_image_name)
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
                            F_RWC_FORMAT % (first_image, second_image),
                            COLTYPE_FLOAT,
                        ),
                        (
                            object_name,
                            F_RWC_FORMAT % (second_image, first_image),
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
            results += ["RWC"]
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
    

