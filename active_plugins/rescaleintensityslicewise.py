"""
RescaleIntensitySlicewise
================

**RescaleIntensity** changes the intensity range of an image to your
desired specifications. This does the same, but slicewise.

This module lets you rescale the intensity of the input images by any of
several methods. You should use caution when interpreting intensity and
texture measurements derived from images that have been rescaled because
certain options for this module do not preserve the relative intensities
from image to image.

As this module rescales data it will not attempt to normalize displayed previews
(as this could make it appear that the scaling had done nothing). As a result images rescaled
to large ranges may appear dim after scaling. To normalize values for viewing,
right-click an image and choose an image contrast transform.

|

============ ============ ===============
Supports 2D? Supports 3D? Respects masks?
============ ============ ===============
YES          YES          YES
============ ============ ===============
"""

import numpy
import skimage.exposure
from cellprofiler_core.image import Image
from cellprofiler_core.module import ImageProcessing
from cellprofiler_core.setting import Measurement
from cellprofiler_core.setting.choice import Choice
from cellprofiler_core.setting.range import FloatRange
from cellprofiler_core.setting.subscriber import ImageSubscriber
from cellprofiler_core.setting.text import Float

M_STRETCH = "Stretch each image to use the full intensity range"
M_MANUAL_INPUT_RANGE = "Choose specific values to be reset to the full intensity range"
M_MANUAL_IO_RANGE = "Choose specific values to be reset to a custom range"
M_DIVIDE_BY_IMAGE_MINIMUM = "Divide by the image's minimum"
M_DIVIDE_BY_IMAGE_MAXIMUM = "Divide by the image's maximum"
M_DIVIDE_BY_VALUE = "Divide each image by the same value"
M_DIVIDE_BY_MEASUREMENT = "Divide each image by a previously calculated value"

M_ALL = [
    M_STRETCH,
    M_MANUAL_INPUT_RANGE,
    M_MANUAL_IO_RANGE,
    M_DIVIDE_BY_IMAGE_MINIMUM,
    M_DIVIDE_BY_IMAGE_MAXIMUM,
    M_DIVIDE_BY_VALUE,
    M_DIVIDE_BY_MEASUREMENT,
]

R_SCALE = "Scale similarly to others"
R_MASK = "Mask pixels"
R_SET_TO_ZERO = "Set to zero"
R_SET_TO_CUSTOM = "Set to custom value"
R_SET_TO_ONE = "Set to one"

LOW_EACH_IMAGE = "Minimum for each image"
CUSTOM_VALUE = "Custom"
PERCENTILE_VALUE = "Percentiles"
LOW_ALL = [CUSTOM_VALUE, PERCENTILE_VALUE, LOW_EACH_IMAGE]

HIGH_EACH_IMAGE = "Maximum for each image"

HIGH_ALL = [CUSTOM_VALUE, PERCENTILE_VALUE, HIGH_EACH_IMAGE]


class RescaleIntensitySlicewise(ImageProcessing):
    module_name = "RescaleIntensitySlicewise"

    variable_revision_number = 1

    def create_settings(self):
        super(RescaleIntensitySlicewise, self).create_settings()

        self.rescale_method = Choice(
            "Rescaling method",
            choices=M_ALL,
            doc="""\
There are a number of options for rescaling the input image:

-  *%(M_STRETCH)s:* Find the minimum and maximum values within the
   unmasked part of the image (or the whole image if there is no mask)
   and rescale every pixel so that the minimum has an intensity of zero
   and the maximum has an intensity of one. If performed on color images
   each channel will be considered separately.
-  *%(M_MANUAL_INPUT_RANGE)s:* Pixels are scaled from an original range
   or percentiles (which you provide) to the range 0 to 1. Options are
   available to handle values outside of the original range.
   To convert 12-bit images saved in 16-bit format to the correct range,
   use the range 0 to 0.0625. The value 0.0625 is equivalent to
   2\ :sup:`12` divided by 2\ :sup:`16`, so it will convert a 16 bit
   image containing only 12 bits of data to the proper range.
-  *%(M_MANUAL_IO_RANGE)s:* Pixels are scaled from their original
   range to the new target range. Options are available to handle values
   outside of the original range.
-  *%(M_DIVIDE_BY_IMAGE_MINIMUM)s:* Divide the intensity value of
   each pixel by the image’s minimum intensity value so that all pixel
   intensities are equal to or greater than 1. The rescaled image can
   serve as an illumination correction function in
   **CorrectIlluminationApply**.
-  *%(M_DIVIDE_BY_IMAGE_MAXIMUM)s:* Divide the intensity value of
   each pixel by the image’s maximum intensity value so that all pixel
   intensities are less than or equal to 1.
-  *%(M_DIVIDE_BY_VALUE)s:* Divide the intensity value of each pixel
   by a value that you choose.
-  *%(M_DIVIDE_BY_MEASUREMENT)s:* The intensity value of each pixel
   is divided by some previously calculated measurement. This
   measurement can be the output of some other module or can be a value
   loaded by the **Metadata** module.
"""
            % globals(),
        )

        self.wants_automatic_low = Choice(
            "Method to calculate the minimum intensity",
            LOW_ALL,
            doc="""\
*(Used only if “%(M_MANUAL_IO_RANGE)s” is selected)*

This setting controls how the minimum intensity is determined.

-  *%(CUSTOM_VALUE)s:* Enter the minimum intensity manually below.
-  *%(PERCENTILE_VALUE)s:* Enter the percentile of the range to be used
   as the minimum intensity for rescaling
-  *%(LOW_EACH_IMAGE)s*: use the lowest intensity in this image as the
   minimum intensity for rescaling
"""
            % globals(),
        )

        self.wants_automatic_high = Choice(
            "Method to calculate the maximum intensity",
            HIGH_ALL,
            doc="""\
*(Used only if “%(M_MANUAL_IO_RANGE)s” is selected)*

This setting controls how the maximum intensity is determined.

-  *%(CUSTOM_VALUE)s*: Enter the maximum intensity manually below.
-  *%(PERCENTILE_VALUE)s:* Enter the percentile of the range to be used
   as the maximum intensity for rescaling
-  *%(HIGH_EACH_IMAGE)s*: Use the highest intensity in this image as
   the maximum intensity for rescaling
"""
            % globals(),
        )

        self.source_low = Float(
            "Lower intensity limit for the input image",
            0,
            doc="""\
*(Used only if "{RESCALE_METHOD}" is "{M_MANUAL_INPUT_RANGE}" or "{M_MANUAL_IO_RANGE}" and
"{WANTS_AUTOMATIC_LOW}" is "{CUSTOM_VALUE}")*

The value of pixels in the input image that you want to rescale to the minimum pixel
value in the output image. Pixel intensities less than this value in the input image are
also rescaled to the minimum pixel value in the output image.
""".format(
                **{
                    "CUSTOM_VALUE": CUSTOM_VALUE,
                    "M_MANUAL_INPUT_RANGE": M_MANUAL_INPUT_RANGE,
                    "M_MANUAL_IO_RANGE": M_MANUAL_IO_RANGE,
                    "RESCALE_METHOD": self.rescale_method.text,
                    "WANTS_AUTOMATIC_LOW": self.wants_automatic_low.text,
                }
            ),
        )

        self.source_high = Float(
            "Upper intensity limit for the input image",
            1,
            doc="""\
*(Used only if "{RESCALE_METHOD}" is "{M_MANUAL_INPUT_RANGE}" or "{M_MANUAL_IO_RANGE}" and
"{WANTS_AUTOMATIC_HIGH}" is "{CUSTOM_VALUE}")*

The value of pixels in the input image that you want to rescale to the maximum pixel
value in the output image. Pixel intensities less than this value in the input image are
also rescaled to the maximum pixel value in the output image.
""".format(
                **{
                    "CUSTOM_VALUE": CUSTOM_VALUE,
                    "M_MANUAL_INPUT_RANGE": M_MANUAL_INPUT_RANGE,
                    "M_MANUAL_IO_RANGE": M_MANUAL_IO_RANGE,
                    "RESCALE_METHOD": self.rescale_method.text,
                    "WANTS_AUTOMATIC_HIGH": self.wants_automatic_high.text,
                }
            ),
        )

        self.source_scale = FloatRange(
            "Intensity range for the input image",
            (0, 1),
            doc="""\
*(Used only if "{RESCALE_METHOD}" is "{M_MANUAL_INPUT_RANGE}" or "{M_MANUAL_IO_RANGE}" and
"{WANTS_AUTOMATIC_LOW}" is "{CUSTOM_VALUE}" and "{WANTS_AUTOMATIC_HIGH}" is "{CUSTOM_VALUE}")*

Select the range of pixel intensities in the input image to rescale to the range of output
pixel intensities. Pixel intensities outside this range will be clipped to the new minimum
or maximum, respectively.
""".format(
                **{
                    "CUSTOM_VALUE": CUSTOM_VALUE,
                    "M_MANUAL_INPUT_RANGE": M_MANUAL_INPUT_RANGE,
                    "M_MANUAL_IO_RANGE": M_MANUAL_IO_RANGE,
                    "RESCALE_METHOD": self.rescale_method.text,
                    "WANTS_AUTOMATIC_HIGH": self.wants_automatic_high.text,
                    "WANTS_AUTOMATIC_LOW": self.wants_automatic_low.text,
                }
            ),
        )

        self.source_percentile_low = Float(
            "Lower percentile intensity limit for the input image",
            0,
            doc="""\
*(Used only if "{RESCALE_METHOD}" is "{M_MANUAL_INPUT_RANGE}" or "{M_MANUAL_IO_RANGE}" and
"{WANTS_AUTOMATIC_LOW}" is "{PERCENTILE_VALUE}")*

The percentile of pixels in the input image that you want to rescale to the minimum pixel
value in the output image. Pixel intensities less than this value in the input image are
also rescaled to the minimum pixel value in the output image.
""".format(
                **{
                    "PERCENTILE_VALUE": PERCENTILE_VALUE,
                    "M_MANUAL_INPUT_RANGE": M_MANUAL_INPUT_RANGE,
                    "M_MANUAL_IO_RANGE": M_MANUAL_IO_RANGE,
                    "RESCALE_METHOD": self.rescale_method.text,
                    "WANTS_AUTOMATIC_LOW": self.wants_automatic_low.text,
                }
            ),
        )

        self.source_percentile_high = Float(
            "Upper intensity limit for the input image",
            100,
            doc="""\
*(Used only if "{RESCALE_METHOD}" is "{M_MANUAL_INPUT_RANGE}" or "{M_MANUAL_IO_RANGE}" and
"{WANTS_AUTOMATIC_HIGH}" is "{PERCENTILE_VALUE}")*

The percentile of pixels in the input image that you want to rescale to the maximum pixel
value in the output image. Pixel intensities less than this value in the input image are
also rescaled to the maximum pixel value in the output image.
""".format(
                **{
                    "PERCENTILE_VALUE": PERCENTILE_VALUE,
                    "M_MANUAL_INPUT_RANGE": M_MANUAL_INPUT_RANGE,
                    "M_MANUAL_IO_RANGE": M_MANUAL_IO_RANGE,
                    "RESCALE_METHOD": self.rescale_method.text,
                    "WANTS_AUTOMATIC_HIGH": self.wants_automatic_high.text,
                }
            ),
        )

        self.source_percentile_scale = FloatRange(
            "Percentile range for the input image",
            (0, 100),
            doc="""\
*(Used only if "{RESCALE_METHOD}" is "{M_MANUAL_INPUT_RANGE}" or "{M_MANUAL_IO_RANGE}" and
"{WANTS_AUTOMATIC_LOW}" is "{PERCENTILE_VALUE}" and "{WANTS_AUTOMATIC_HIGH}" is "{PERCENTILE_VALUE}")*

Select the pixel intensity percentiles in the input image to rescale to the range of output
pixel intensities. Pixel intensities outside this range will be clipped to the new minimum
or maximum, respectively.
""".format(
                **{
                    "PERCENTILE_VALUE": PERCENTILE_VALUE,
                    "M_MANUAL_INPUT_RANGE": M_MANUAL_INPUT_RANGE,
                    "M_MANUAL_IO_RANGE": M_MANUAL_IO_RANGE,
                    "RESCALE_METHOD": self.rescale_method.text,
                    "WANTS_AUTOMATIC_HIGH": self.wants_automatic_high.text,
                    "WANTS_AUTOMATIC_LOW": self.wants_automatic_low.text,
                }
            ),
        )

        self.dest_scale = FloatRange(
            "Intensity range for the output image",
            (0, 1),
            doc="""\
*(Used only if "{RESCALE_METHOD}" is "{M_MANUAL_IO_RANGE}")*

Set the range of pixel intensities in the output image. The minimum pixel intensity of the input
image will be rescaled to the minimum output image intensity. The maximum pixel intensity of the
output image will be rescaled to the maximum output image intensity.
""".format(
                **{
                    "M_MANUAL_IO_RANGE": M_MANUAL_IO_RANGE,
                    "RESCALE_METHOD": self.rescale_method.text,
                }
            ),
        )

        self.divisor_value = Float(
            "Divisor value",
            1,
            minval=numpy.finfo(float).eps,
            doc="""\
*(Used only if “%(M_DIVIDE_BY_VALUE)s” is selected)*

Enter the value to use as the divisor for the final image.
"""
            % globals(),
        )

        self.divisor_measurement = Measurement(
            "Divisor measurement",
            lambda: "Image",
            doc="""\
*(Used only if “%(M_DIVIDE_BY_MEASUREMENT)s” is selected)*

Select the measurement value to use as the divisor for the final image.
"""
            % globals(),
        )

    def settings(self):
        __settings__ = super(RescaleIntensitySlicewise, self).settings()

        return __settings__ + [
            self.rescale_method,
            self.wants_automatic_low,
            self.wants_automatic_high,
            self.source_low,
            self.source_high,
            self.source_scale,
            self.dest_scale,
            self.divisor_value,
            self.divisor_measurement,
            self.source_percentile_low,
            self.source_percentile_high,
            self.source_percentile_scale,
        ]

    def visible_settings(self):
        __settings__ = super(RescaleIntensitySlicewise, self).visible_settings()

        __settings__ += [self.rescale_method]
        if self.rescale_method in (M_MANUAL_INPUT_RANGE, M_MANUAL_IO_RANGE):
            __settings__ += [self.wants_automatic_low]
            # Low automatic, go straight to high (and handle there)
            if self.wants_automatic_low.value == LOW_EACH_IMAGE: 
                __settings__ += [self.wants_automatic_high]
                if self.wants_automatic_high.value == CUSTOM_VALUE:
                    __settings__ += [self.source_high]
                elif self.wants_automatic_high.value == PERCENTILE_VALUE:
                    __settings__ += [self.source_percentile_high]
            if self.wants_automatic_low.value == CUSTOM_VALUE:
                if self.wants_automatic_high.value == CUSTOM_VALUE:
                    __settings__ += [self.wants_automatic_high, self.source_scale]
                if self.wants_automatic_high.value == HIGH_EACH_IMAGE:
                    __settings__ += [self.source_low, self.wants_automatic_high]
                if self.wants_automatic_high.value == PERCENTILE_VALUE:
                    __settings__ += [self.source_low, self.wants_automatic_high, self.source_percentile_high]
            if self.wants_automatic_low.value == PERCENTILE_VALUE:
                if self.wants_automatic_high.value == PERCENTILE_VALUE:
                    __settings__ += [self.wants_automatic_high, self.source_percentile_scale]
                if self.wants_automatic_high.value == HIGH_EACH_IMAGE:
                    __settings__ += [self.source_percentile_low, self.wants_automatic_high]
                if self.wants_automatic_high.value == CUSTOM_VALUE:
                    __settings__ += [self.source_percentile_low, self.wants_automatic_high, self.source_high]


        if self.rescale_method == M_MANUAL_IO_RANGE:
            __settings__ += [self.dest_scale]

        elif self.rescale_method == M_DIVIDE_BY_MEASUREMENT:
            __settings__ += [self.divisor_measurement]
        elif self.rescale_method == M_DIVIDE_BY_VALUE:
            __settings__ += [self.divisor_value]
        return __settings__

    def run(self, workspace):
        input_image = workspace.image_set.get_image(self.x_name.value, must_be_grayscale=True)
        if input_image.dimensions == 2:
            pixel_data = numpy.expand_dims(input_image.pixel_data, axis=0)
            mask = numpy.expand_dims(input_image.mask, axis=0)
        else:
            pixel_data = input_image.pixel_data
            mask = input_image.mask
        
        output_planes = []
        input_planes = numpy.split(pixel_data, pixel_data.shape[0], 0)
        mask_planes = numpy.split(mask, pixel_data.shape[0], 0)
        for plane in range(len(input_planes)):
            masked_pixel_data = numpy.squeeze(input_planes[plane] * mask_planes[plane])

            if self.rescale_method.value in [M_STRETCH, M_MANUAL_INPUT_RANGE, M_MANUAL_IO_RANGE]:
                if (input_planes[plane][mask_planes[plane]]).size == 0:
                    in_range = (0, 1)
                elif self.rescale_method.value == M_STRETCH:
                    in_range = (numpy.min(masked_pixel_data),numpy.max(masked_pixel_data))
                else:
                    in_range = self.get_source_range(masked_pixel_data)

            if self.rescale_method == M_STRETCH:
                output_plane = self.rescale(masked_pixel_data, in_range)
            elif self.rescale_method == M_MANUAL_INPUT_RANGE:
                output_plane = self.manual_input_range(masked_pixel_data, in_range)
            elif self.rescale_method == M_MANUAL_IO_RANGE:
                output_plane = self.manual_io_range(masked_pixel_data, in_range)
            elif self.rescale_method == M_DIVIDE_BY_IMAGE_MINIMUM:
                output_plane = self.divide_by_image_minimum(masked_pixel_data)
            elif self.rescale_method == M_DIVIDE_BY_IMAGE_MAXIMUM:
                output_plane = self.divide_by_image_maximum(masked_pixel_data)
            elif self.rescale_method == M_DIVIDE_BY_VALUE:
                output_plane = self.divide_by_value(masked_pixel_data)
            elif self.rescale_method == M_DIVIDE_BY_MEASUREMENT:
                output_plane = self.divide_by_measurement(workspace, masked_pixel_data)
            
            output_planes.append(output_plane)

        output_image = numpy.stack(output_planes,axis=0)
        
        if input_image.dimensions == 2:
            output_image = numpy.squeeze(output_image)

        rescaled_image = Image(
            output_image,
            parent_image=input_image,
            convert=False,
            dimensions=input_image.dimensions,
        )

        workspace.image_set.add(self.y_name.value, rescaled_image)

        if self.show_window:
            workspace.display_data.x_data = input_image.pixel_data

            workspace.display_data.y_data = output_image

            workspace.display_data.dimensions = input_image.dimensions

    def display(self, workspace, figure):
        figure.set_subplots((2, 1))

        figure.set_subplots(
            dimensions=workspace.display_data.dimensions, subplots=(2, 1)
        )

        figure.subplot_imshow(
            image=workspace.display_data.x_data,
            title=self.x_name.value,
            normalize=False,
            colormap="gray",
            x=0,
            y=0,
        )

        figure.subplot_imshow(
            image=workspace.display_data.y_data,
            sharexy=figure.subplot(0, 0),
            title=self.y_name.value,
            colormap="gray",
            normalize=False,
            x=1,
            y=0,
        )

    def rescale(self, input_pixels, in_range, out_range=(0.0, 1.0)):
        data = 1.0 * input_pixels

        rescaled = skimage.exposure.rescale_intensity(
            data, in_range=in_range, out_range=out_range
        )

        return rescaled

    def manual_input_range(self, input_image, in_range):

        return self.rescale(input_image, in_range)

    def manual_io_range(self, input_image, in_range):

        out_range = (self.dest_scale.min, self.dest_scale.max)

        return self.rescale(input_image, in_range, out_range)

    def divide(self, data, value):
        if value == 0.0:
            raise ZeroDivisionError("Cannot divide pixel intensity by 0.")

        return data / float(value)

    def divide_by_image_minimum(self, input_pixels):

        src_min = max(numpy.min(input_pixels),0)

        return self.divide(input_pixels, src_min)

    def divide_by_image_maximum(self, input_pixels):

        src_max = min(numpy.max(input_pixels),1)

        return self.divide(input_pixels, src_max)

    def divide_by_value(self, input_pixels):
        return self.divide(input_pixels, self.divisor_value.value)

    def divide_by_measurement(self, workspace, input_pixels):
        m = workspace.measurements

        value = m.get_current_image_measurement(self.divisor_measurement.value)

        return self.divide(input_pixels, value)

    def get_source_range(self, input_pixels):
        """Get the source range, accounting for automatically computed values"""
        if (
            self.wants_automatic_high == CUSTOM_VALUE
            and self.wants_automatic_low == CUSTOM_VALUE
        ):
            return self.source_scale.min, self.source_scale.max

        if (
            self.wants_automatic_high == PERCENTILE_VALUE
            and self.wants_automatic_low == PERCENTILE_VALUE
        ):
            return numpy.percentile(input_pixels, self.source_percentile_scale.min), numpy.percentile(input_pixels, self.source_percentile_scale.max)
        
        if self.wants_automatic_low == PERCENTILE_VALUE:
            src_min = numpy.percentile(input_pixels,self.source_percentile_low.value)
        elif self.wants_automatic_low == LOW_EACH_IMAGE:
            src_min = numpy.min(input_pixels)
        else:
            src_min = self.source_low.value

        if self.wants_automatic_high == PERCENTILE_VALUE:
            src_max = numpy.percentile(input_pixels,self.source_percentile_high.value)
        elif self.wants_automatic_high == HIGH_EACH_IMAGE:
            src_max = numpy.max(input_pixels)
        else:
            src_max = self.source_high.value
        return src_min, src_max
