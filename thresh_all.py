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
import cellprofiler.measurement
import cellprofiler.module
import cellprofiler.setting
import cellprofiler.modules.threshold as threshold

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
        super(ImageTemplate, self).create_settings()

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

**ImageTemplate** will do something to this image.
"""

        #
        # Here's a choice box - the user gets a drop-down list of what
        # can be done.
        #
        self.gradient_choice = cellprofiler.setting.Choice(
            text="Gradient choice:",
            # The choice takes a list of possibilities. The first one
            # is the default - the one the user will typically choose.
            choices=[GRADIENT_DIRECTION_X, GRADIENT_DIRECTION_Y, GRADIENT_MAGNITUDE],
            # The default value is the first choice in choices. You can
            # specify a different initial value using the value keyword.
            value=GRADIENT_MAGNITUDE,
            #
            # Here, in the documentation, we do a little trick so that
            # we use the actual text that's displayed in the documentation.
            #
            # {GRADIENT_MAGNITUDE} will get changed into "Gradient magnitude"
            # etc. Python will look in keyword arguments for format()
            # for the "GRADIENT_" names and paste them in where it sees
            # a matching {GRADIENT_...}.
            #
            doc="""\
Choose what to calculate:

-  *{GRADIENT_MAGNITUDE}*: calculate the magnitude of the gradient at
   each pixel.
-  *{GRADIENT_DIRECTION_X}*: get the relative contribution of the
   gradient in the X direction (.5 = no contribution, 0 to .5 =
   decreasing with increasing X, .5 to 1 = increasing with increasing
   X).
-  *{GRADIENT_DIRECTION_Y}*: get the relative contribution of the
   gradient in the Y direction.
""".format(**{
                "GRADIENT_MAGNITUDE": GRADIENT_MAGNITUDE,
                "GRADIENT_DIRECTION_X": GRADIENT_DIRECTION_X,
                "GRADIENT_DIRECTION_Y": GRADIENT_DIRECTION_Y
            })
        )

        #
        # A binary setting displays a checkbox.
        #
        self.automatic_smoothing = cellprofiler.setting.Binary(
            text="Automatically choose the smoothing scale?",
            value=True,  # The default value is to choose automatically
            doc="The module will automatically choose a smoothing scale for you if you leave this checked."
        )

        #
        # We do a little smoothing which supplies a scale to the gradient.
        #
        # We use a float setting so that the user can give us a number
        # for the scale. The control will turn red if the user types in
        # an invalid scale.
        #
        self.scale = cellprofiler.setting.Float(
            text="Scale",
            value=1,  # The default value is 1 - a short-range scale
            minval=0.1,  # We don't let the user type in really small values
            maxval=100,  # or large values
            doc="""\
This is a scaling factor that supplies the sigma for a gaussian that's
used to smooth the image. The gradient is calculated on the smoothed
image, so large scales will give you long-range gradients and small
scales will give you short-range gradients.
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
        settings = super(ImageTemplate, self).settings()

        # Append additional settings here.
        return settings + [
            self.gradient_choice,
            self.automatic_smoothing,
            self.scale
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
        visible_settings = super(ImageTemplate, self).visible_settings()

        # Configure the visibility of additional settings below.
        visible_settings += [
            self.gradient_choice,
            self.automatic_smoothing
        ]

        #
        # Show the user the scale only if self.wants_smoothing is checked
        #
        if not self.automatic_smoothing:
            visible_settings += [self.scale]

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
        self.function = gradient_image

        super(ImageTemplate, self).run(workspace)

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
def gradient_image(pixels, gradient_choice, automatic_smoothing, scale):
    #
    # Get the smoothing parameter
    #
    if automatic_smoothing:
        # Pick the mode of the power spectrum - obviously this
        # is pretty hokey, not intended to really find a good number.
        #
        fft = numpy.fft.fft2(pixels)
        power2 = numpy.sqrt((fft * fft.conjugate()).real)
        mode = numpy.argwhere(power2 == power2.max())[0]
        scale = numpy.sqrt(numpy.sum((mode + .5) ** 2))

    gradient_magnitude = scipy.ndimage.gaussian_gradient_magnitude(pixels, scale)

    if gradient_choice == GRADIENT_MAGNITUDE:
        gradient_image = gradient_magnitude
    else:
        # Image data is indexed by rows and columns, with a given point located at
        # position (row, column). Here, x represents the column coordinate (at index 1)
        # and y represents the row coordinate (at index 0).
        #
        # You can learn more about image coordinate systems here:
        # http://scikit-image.org/docs/dev/user_guide/numpy_images.html#coordinate-conventions
        x = scipy.ndimage.correlate1d(gradient_magnitude, [-1, 0, 1], 1)
        y = scipy.ndimage.correlate1d(gradient_magnitude, [-1, 0, 1], 0)
        norm = numpy.sqrt(x ** 2 + y ** 2)
        if gradient_choice == GRADIENT_DIRECTION_X:
            gradient_image = .5 + x / norm / 2
        else:
            gradient_image = .5 + y / norm / 2

    return gradient_image
