# coding=utf-8

#################################
#
# Imports from useful Python libraries
#
#################################

import centrosome
import numpy
import scipy.ndimage

#################################
#
# Imports from CellProfiler
#
##################################

import cellprofiler.image
import cellprofiler.measurement
import cellprofiler.module
import cellprofiler.setting
from cellprofiler.modules.threshold import Threshold

RB_MEAN = "Mean"
RB_MEDIAN = "Median"
RB_MODE = "Mode"
RB_SD = "Standard deviation"
RB_MAD = "Median absolute deviation"

threshlist = [
    "Global 2-class Otsu", 
    "Global 3-class Otsu (middle to fore)", 
    "Global 3-class Otsu (middle to back)",
    "Local 2-class Otsu", 
    "Local 3-class Otsu (middle to fore)", 
    "Local 3-class Otsu (middle to back)",
    "Minimum cross entropy",
    "Manual", 
    "Measurement",
    "RobustBackground"
    ]

__doc__ = """\
TestAllThresholds
=================

**TestAllThresholds** is a module that allows you to test many thresholds, and pass
one forward as the finally selected method to other thresholds.
|

============ ============ ===============
Supports 2D? Supports 3D? Respects masks?
============ ============ ===============
YES          NO           YES
============ ============ ===============

See also
^^^^^^^^

All the thresholds here are implemented and taken from **Threshold**. 
See that module's help for more information

What do I need as input?
^^^^^^^^^^^^^^^^^^^^^^^^

An input greyscale image; if you want to use a measurement to threshold on, it should be
calculated before this module (eg. calculated by MeasureImageIntensity, or loaded as a 
piece of metadata).

What do I get as output?
^^^^^^^^^^^^^^^^^^^^^^^^

A thresholded image; when the eye is open, you can see the results of multiple thresholds.
You will automatically view in the display Minimum Cross Entropy, Otsu 2-class, 
Otsu 3 class (middle to foreground), and Otsu 3-class (middle to background).
You can optionally add adaptive versions of the 3 Otsus, with a specified window size.
You can also optionally add manual thresholds, measurement based thresholds, and RobustBackground.


Measurements made by this module
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Technical notes
^^^^^^^^^^^^^^^

Inspired by scikit-image's version, as well as ImageJ's AutoThreshold.

"""

#
# The module class.
#
class TestAllThresholds(cellprofiler.module.ImageProcessing):

    module_name = "TestAllThresholds"
    variable_revision_number = 1

    #
    # "create_settings" is where you declare the user interface elements
    # (the "settings") which the user will use to customize your module.
    #
    # You can look at other modules and in cellprofiler.settings for
    # settings you can use.
    #
    def create_settings(self):
        #
        # The superclass (cellprofiler.module.ImageProcessing) defines two
        # settings for image input and output:
        #
        # -  x_name: an ImageNameSubscriber which "subscribes" to all
        #    ImageNameProviders in prior modules. Modules before yours will
        #    put images into CellProfiler. The ImageNameSubscriber gives
        #    your user a list of these images which can then be used as inputs
        #    in your module.
        # -  y_name: an ImageNameProvider makes the image available to subsequent
        #    modules.
        super(TestAllThresholds, self).create_settings()

        #
        # reST help that gets displayed when the user presses the
        # help button to the right of the edit box.
        #
        # The superclass defines some generic help test. You can add
        # module-specific help text by modifying the setting's "doc"
        # string.
        #
        self.x_name.doc = """What image do you want to threshold?"""

        #
        # Here's a choice box - the user gets a drop-down list of what
        # can be done.
        #
        self.do_adaptive = cellprofiler.setting.Binary(
            text="Do you want to test adaptive thresholding?",
            value=True,  # The default value is to choose automatically
            doc="""\
Choose *"Yes"* to try adaptive thresholding, using a user-provided window 
size.
"""
        )

        self.adaptive_window_size = cellprofiler.setting.Integer(
            text="Adaptive window size",
            value=50,  
            minval=1,  # We don't let the user type in really small values
            maxval=1000,  # or large values
            doc="""\
Enter the size of the window (in pixels) to be used for the adaptive method. 
Often a good choice is some multiple of the largest expected object size.
Note that windows greater than half the image size may report an error.
"""
        )

        self.do_manual = cellprofiler.setting.Binary(
            text="Do you want to test manual thresholding?",
            value=True,  # The default value is to choose automatically
            doc="""\
Choose *"Yes"* to try manual thresholding, using a user-provided value 
"""
        )

        self.manual_threshold = cellprofiler.setting.Float(
            text="Manual threshold",
            value=0.2,  
            minval=0,  # We don't let the user type in really small values
            maxval=1,  # or large values
            doc="""\
Enter the manual threshold to try
"""
        )

        self.do_measured = cellprofiler.setting.Binary(
            text="Do you want to test thresholding based on a measurement?",
            value=True,  # The default value is to choose automatically
            doc="""\
Choose *"Yes"* to try a threshold based on a previously measured value. 
"""
        )

        def object_function():
            return cellprofiler.measurement.IMAGE

        self.measured_threshold = cellprofiler.setting.Measurement(
            text="Select the measurement to use to threshold.",
            object_fn= object_function,
            doc = """\
Choose a measurement previously created in the pipeline, or uploaded
as a piece of metadata
"""
        )

        self.do_robust = cellprofiler.setting.Binary(
            text="Do you want to test RobustBackground thresholding?",
            value=True,  # The default value is to choose automatically
            doc="""\
Choose *"Yes"* to try a threshold based on a previously measured value. 
"""
        )

        self.lower_outlier_fraction = cellprofiler.setting.Float(
            "Lower outlier fraction",
            0.05,
            minval=0,
            maxval=1,
            doc="""\
*(Used only when customizing the "RobustBackground" method)*

Discard this fraction of the pixels in the image starting with those of
the lowest intensity.
"""
        )

        self.upper_outlier_fraction = cellprofiler.setting.Float(
            "Upper outlier fraction",
            0.05,
            minval=0,
            maxval=1,
            doc="""\
*(Used only when customizing the "RobustBackground" method)*

Discard this fraction of the pixels in the image starting with those of
the highest intensity.
"""
        )

        self.averaging_method = cellprofiler.setting.Choice(
            "Averaging method",
            [RB_MEAN, RB_MEDIAN, RB_MODE],
            doc="""\
*(Used only when customizing the "RobustBackground" method)*

This setting determines how the intensity midpoint is determined.

-  *{RB_MEAN}*: Use the mean of the pixels remaining after discarding
   the outliers. This is a good choice if the cell density is variable
   or high.
-  *{RB_MEDIAN}*: Use the median of the pixels. This is a good choice
   if, for all images, more than half of the pixels are in the
   background after removing outliers.
-  *{RB_MODE}*: Use the most frequently occurring value from among the
   pixel values. The RobustBackground method groups the
   intensities into bins (the number of bins is the square root of the
   number of pixels in the unmasked portion of the image) and chooses
   the intensity associated with the bin with the most pixels.
""".format(**{
                "RB_MEAN": RB_MEAN,
                "RB_MEDIAN": RB_MEDIAN,
                "RB_MODE": RB_MODE
            }
            )       
        )

        self.variance_method = cellprofiler.setting.Choice(
            "Variance method",
            [RB_SD, RB_MAD],
            doc="""\
*(Used only when customizing the "RobustBackground" method)*

Robust background adds a number of deviations (standard or MAD) to the
average to get the final background. This setting chooses the method
used to assess the variance in the pixels, after removing outliers.
Choose one of *{RB_SD}* or *{RB_MAD}* (the median of the absolute
difference of the pixel intensities from their median).
""".format(**{
                "RB_MAD": RB_MAD,
                "RB_SD": RB_SD
            })
        )

        self.number_of_deviations = cellprofiler.setting.Float(
            "# of deviations",
            2,
            doc="""\
*(Used only when customizing the "RobustBackground" method)*

Robust background calculates the variance, multiplies it by the value
given by this setting and adds it to the average. Adding several
deviations raises the threshold well above the average.
Use a larger number to be more stringent about identifying foreground pixels.
Use a smaller number to be less stringent. It’s even possible to
use a negative number if you want the threshold to be lower than the average
(e.g., for images that are densely covered by foreground).
"""
        )

        self.threshold_smoothing_scale = cellprofiler.setting.Float(
            "Threshold smoothing scale",
            0,
            minval=0,
            doc="""\
This setting controls the scale used to smooth the input image before
the threshold is applied.
The input image can be optionally smoothed before being thresholded.
Smoothing can improve the uniformity of the resulting objects, by
removing holes and jagged edges caused by noise in the acquired image.
Smoothing is most likely *not* appropriate if the input image is binary,
if it has already been smoothed or if it is an output of a pixel-based classifier.
The scale should be approximately the size of the artifacts to be
eliminated by smoothing. A Gaussian is used with a sigma adjusted so
that 1/2 of the Gaussian’s distribution falls within the diameter given
by the scale (sigma = scale / 0.674)
Use a value of 0 for no smoothing. Use a value of 1.3488 for smoothing
with a sigma of 1.
"""
        )

        self.threshold_correction_factor = cellprofiler.setting.Float(
            "Threshold correction factor",
            1,
            doc="""\
This setting allows you to adjust the threshold as calculated by the
above method. The value entered here adjusts the threshold either
upwards or downwards, by multiplying it by this value. A value of 1
means no adjustment, 0 to 1 makes the threshold more lenient and > 1
makes the threshold more stringent.

When the threshold is calculated automatically, you may find that the value 
is consistently
too stringent or too lenient across all images. This setting is helpful
for adjusting the threshold to a value that you empirically determine is
more suitable. For example, the {Otsu automatic thresholding
inherently assumes that 50% of the image is covered by objects. If a
larger percentage of the image is covered, the Otsu method will give a
slightly biased threshold that may have to be corrected using this
setting.
"""
        )

        self.threshold_range = cellprofiler.setting.FloatRange(
            "Lower and upper bounds on threshold",
            (0, 1),
            minval=0,
            maxval=1,
            doc="""\
Enter the minimum and maximum allowable threshold, a value from 0 to 1.
This is helpful as a safety precaution: when the threshold as calculated
automatically is clearly outside a reasonable range, the min/max allowable
threshold will override the automatic threshold.

For example, if there are no objects in the field of view, the automatic
threshold might be calculated as unreasonably low; the algorithm will
still attempt to divide the foreground from background (even though
there is no foreground), and you may end up with spurious false positive
foreground regions. In such cases, you can estimate the background pixel
intensity and set the lower bound according to this
empirically-determined value.
"""
        )

        self.choose_final_threshold = cellprofiler.setting.Choice(
            "Which threshold should be used to generate your output image?",
            choices=threshlist, value = 'Minimum cross entropy'
        )

    #
    # The "settings" method tells CellProfiler about the settings you
    # have in your module. CellProfiler uses the list for saving
    # and restoring values for your module when it saves or loads a
    # pipeline file.
    #
    def settings(self):
        #
        # The superclass's "settings" method returns [self.x_name, self.y_name],
        # which are the input and output image settings.
        #
        return [
            self.x_name, self.do_adaptive, self.adaptive_window_size,
            self.do_manual, self.manual_threshold, self.do_measured,
            self.measured_threshold, self.do_robust, self.lower_outlier_fraction,
            self.upper_outlier_fraction, self.averaging_method, self.variance_method,
            self.number_of_deviations, self.threshold_smoothing_scale, self.threshold_correction_factor,
            self.threshold_range, self.y_name, self.choose_final_threshold
            ]

    #
    # "visible_settings" tells CellProfiler which settings should be
    # displayed and in what order.
    #
    # You don't have to implement "visible_settings" - if you delete
    # visible_settings, CellProfiler will use "settings" to pick settings
    # for display.
    #
    def visible_settings(self):
        
        visible_settings = [self.x_name, self.do_adaptive] 
        if self.do_adaptive:
            visible_settings += [self.adaptive_window_size]
        visible_settings += [self.do_manual]
        if self.do_manual:
            visible_settings += [self.manual_threshold] 
        visible_settings += [self.do_measured]
        if self.do_measured:
            visible_settings += [self.measured_threshold]
        visible_settings += [self.do_robust]
        if self.do_robust:
            visible_settings += [self.lower_outlier_fraction,self.upper_outlier_fraction, 
            self.averaging_method, self.variance_method,self.number_of_deviations]
        visible_settings += [self.threshold_smoothing_scale, self.threshold_correction_factor,
            self.threshold_range, self.y_name, self.choose_final_threshold]

        return visible_settings

    #
    # CellProfiler calls "run" on each image set in your pipeline.
    #
    def run(self, workspace):
        
        x_name = self.x_name.value

        images = workspace.image_set

        x = images.get_image(x_name)
        
        final_threshold, original_threshold, output_image = self.get_threshold(x, workspace, self.choose_final_threshold.value)

        print(final_threshold, original_threshold)

    #
    # "volumetric" indicates whether or not this module supports 3D images.
    # Thresholding supports 3D, but our display does not, so let's say false.
    #
    def volumetric(self):
        return False

    def get_threshold(self, image, workspace, method):
        if method == "Manual":
            return self.manual_threshold.value, self.manual_threshold.value, self.apply_threshold(image, self.manual_threshold.value, 0)

        if method == "Measurement":
            m = workspace.measurements

            # Thresholds are stored as single element arrays.  Cast to float to extract the value.
            t_orig = float(m.get_current_image_measurement(self.measured_threshold.value))

            t_final = t_orig * self.threshold_correction_factor.value

            t_final = min(max(t_final, self.threshold_range.min), self.threshold_range.max)

            return t_final, t_orig, self.apply_threshold(image, t_final, 0)

        workspace, module = self.make_workspace(image.pixel_data,mask=image.mask)

        if method == "Minimum cross entropy":
            t_final, t_orig, self.run_mce(image, workspace, module)
            return t_final, t_orig, self.apply_threshold(image, t_final, self.threshold_smoothing_scale)

        """if self.threshold_operation == centrosome.threshold.TM_ROBUST_BACKGROUND:
            return self._threshold_robust_background(image)

        if self.threshold_operation == centrosome.threshold.TM_OTSU:
            if self.two_class_otsu.value == O_TWO_CLASS:
                return self._threshold_otsu(image)

        return self._threshold_otsu3(image)
        
        #Pull from here as we implement them
        [, "Global 3-class Otsu (middle to fore)", "Global 3-class Otsu (middle to back)",
        "Local 2-class Otsu", "Local 3-class Otsu (middle to fore)", "Local 3-class Otsu (middle to back)",
        "RobustBackground"]"""

    def make_workspace(self, image, mask=None, dimensions=2):
        '''Make a workspace for running Threshold. Taken from CellProfiler's test suite.'''
        module = Threshold()
        module.x_name.value = 'input'
        module.y_name.value = 'output'
        module.threshold_range.value = self.threshold_range.value
        module.threshold_correction_factor.value = self.threshold_correction_factor.value
        module.threshold_smoothing_scale.value = self.threshold_smoothing_scale.value
        pipeline = cellprofiler.pipeline.Pipeline()
        object_set = cellprofiler.object.ObjectSet()
        image_set_list = cellprofiler.image.ImageSetList()
        image_set = image_set_list.get_image_set(0)
        workspace = cellprofiler.workspace.Workspace(pipeline,
                                                     module,
                                                     image_set,
                                                     object_set,
                                                     cellprofiler.measurement.Measurements(),
                                                     image_set_list)
        image_set.add('input',
                      cellprofiler.image.Image(image, dimensions=dimensions) if mask is None
                      else cellprofiler.image.Image(image, mask, dimensions=dimensions))
        return workspace, module

    def apply_threshold(self, image, threshold, smoothing):
        data = image.pixel_data

        mask = image.mask

        sigma = smoothing / 0.6744 / 2.0

        blurred_image = centrosome.smooth.smooth_with_function_and_mask(
            data,
            lambda x: scipy.ndimage.gaussian_filter(x, sigma, mode="constant", cval=0),
            mask
        )

        return (blurred_image >= threshold) & mask

    def run_mce(self, image, workspace, module):
        module.threshold_scope.value = "Global"
        module.global_operation.value = "Minimum cross entropy"
        t_final, t_orig = module.get_threshold(image, workspace)
        return t_final, t_orig
    
    