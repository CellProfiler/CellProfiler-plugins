# coding=utf-8

#################################
#
# Imports from useful Python libraries
#
#################################

import numpy
import scipy.ndimage

#################################
#
# Imports from CellProfiler
#
##################################

import cellprofiler.image
import cellprofiler.module
import cellprofiler.setting

__doc__ = """\
RescaleMeanSD
=============
**RescaleMeanSD** is an image processing module that is optimized for rescaling label-free images.
It defines a fixed mean and scales the standard deviation by as set value.
This module should be combined with a "Rescale Intensity" module, trimming between 0 and 1 (option: "specific values to be reset to a custom range").
|
============ ============ ===============
Supports 2D? Supports 3D? Respects masks?
============ ============ ===============
YES          NO           NO
============ ============ ===============
See also
^^^^^^^^
This module is related to the isl_preprocess_flourescent.
What do I need as input?
^^^^^^^^^^^^^^^^^^^^^^^^
A .tiff brightfield image
What do I get as output?
^^^^^^^^^^^^^^^^^^^^^^^^

Technical notes
^^^^^^^^^^^^^^^
This image processing is used in Christiansen et al.: "In silico labeling: Predicting fluorescent labels in unlabeled images".

References
^^^^^^^^^^
Niklas Rindtorff
"""

#
# Constants
#
# It's good programming practice to replace things like strings with
# constants if they will appear more than once in your program. That way,
# if someone wants to change the text, that text will change everywhere.
# Also, you can't misspell it by accident.
#
#GRADIENT_MAGNITUDE = "Gradient magnitude"
#
# The module class.
#
# Your module should "inherit" from cellprofiler.module.Module, or a
# subclass of cellprofiler.module.Module. This module inherits from
# cellprofiler.module.ImageProcessing, which is the base class for
# image processing modules. Image processing modules take an image as
# input and output an image.
#
# This module will use the methods from cellprofiler.module.ImageProcessing
# unless you re-implement them. You can let cellprofiler.module.ImageProcessing
# do most of the work and implement only what you need.
#
# Other classes you can inherit from are:
#
# -  cellprofiler.module.ImageSegmentation: modules which take an image
#    as input and output a segmentation (objects) should inherit from this
#    class.
# -  cellprofiler.module.ObjectProcessing: modules which operate on objects
#    should inherit from this class. These are modules that take objects as
#    input and output new objects.
#
class RescaleMeanSD(cellprofiler.module.ImageProcessing):
    #
    # The module starts by declaring the name that's used for display,
    # the category under which it is stored and the variable revision
    # number which can be used to provide backwards compatibility if
    # you add user-interface functionality later.
    #
    # This module's category is "Image Processing" which is defined
    # by its superclass.
    #
    module_name = "RescaleMeanSD"

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
        super(RescaleMeanSD, self).create_settings()

        #
        # reST help that gets displayed when the user presses the
        # help button to the right of the edit box.
        #
        # The superclass defines some generic help test. You can add
        # module-specific help text by modifying the setting's "doc"
        # string.
        #
        self.x_name.doc = """\
This is the image that the module operates on. You can choose any image
that is made available by a prior module.
**RescaleMeanSD** will do something to this image.
"""
        # We use a float setting so that the user can give us a number
        # for the scale. The control will turn red if the user types in
        # an invalid scale.
        #
        self.mean = cellprofiler.setting.Float(
            text="Mean",
            value=0.5,  # The default value is 1 - a short-range scale
            minval=0.0001,  # We don't let the user type in really small values
            maxval=1,  # or large values
            doc="""\
This is the average intensity the image will have after rescaling. Images will be scaled between 0 and 1.
"""
        )
        # I repeat the same for the standard deviation
        self.sd = cellprofiler.setting.Float(
            text="Standard Deviation",
            value=0.125,  # The default value is 1 - a short-range scale
            minval=0.0001,  # We don't let the user type in really small values
            maxval=0.5,  # or large values
            doc="""\
This is the standard deviation of intensity values after rescaling. Images will be scaled between 0 and 1.
"""
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
        settings = super(RescaleMeanSD, self).settings()

        # Append additional settings here.
        return settings + [
            self.mean,
            self.sd
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
        #
        # The superclass's "visible_settings" method returns [self.x_name,
        # self.y_name], which are the input and output image settings.
        #
        visible_settings = super(RescaleMeanSD, self).visible_settings()

        # Configure the visibility of additional settings below.
        visible_settings += [
            self.mean,
            self.sd
        ]

        return visible_settings

    #
    # CellProfiler calls "run" on each image set in your pipeline.
    #
    def run(self, workspace):
        #
        # The superclass's "run" method handles retreiving the input image
        # and saving the output image. Module-specific behavior is defined
        # by setting "self.function", defined in this module. "self.function"
        # is called after retrieving the input image and before saving
        # the output image.
        #
        # The first argument of "self.function" is always the input image
        # data (as a numpy array). The remaining arguments are the values of
        # the module settings as they are returned from "settings" (excluding
        # "self.y_data", or the output image).
        #
        self.function = normalize_convert_mu_sd_cp

        super(RescaleMeanSD, self).run(workspace)

    #
    # "volumetric" indicates whether or not this module supports 3D images.
    # The "gradient_image" function is inherently 2D, and we've noted this
    # in the documentation for the module. Explicitly return False here
    # to indicate that 3D images are not supported.
    #
    def volumetric(self):
        return False

#
# This is the function that gets called during "run" to create the output image.
# The first parameter must be the input image data. The remaining parameters are
# the additional settings defined in "settings", in the order they are returned.
#
# This function must return the output image data (as a numpy array).
#
def normalize_convert_mu_sd_cp(pixels, mean, sd):
    #I rescale
    #pixels = pixels.astype(numpy.float64_t)
    mat_ms = mean + (pixels - pixels.mean()) * (sd/pixels.std())

    return mat_ms
    #return pixels
