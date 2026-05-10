#################################
#
# Imports from useful Python libraries
#
#################################

import logging
import numpy
import scipy.ndimage

#################################
#
# Imports from CellProfiler
#
##################################

import cellprofiler_core.setting
import cellprofiler_core.module
from cellprofiler_core.image import Image
from cellprofiler_core.setting import Binary
from cellprofiler_core.setting.subscriber import ImageSubscriber
from cellprofiler_core.setting.text import ImageName, Integer

__doc__ = """\
VarianceTransform
=================
**VarianceTransform** allows you to calculate the variance of an image using a set window size. It also has
the option to find the optimal window size to obtain the maximum variance of an image within a given range.

|

============ ============ ===============
Supports 2D? Supports 3D? Respects masks?
============ ============ ===============
YES          YES           YES
============ ============ ===============
"""


class VarianceTransform(cellprofiler_core.module.ImageProcessing):
    module_name = "VarianceTransform"

    variable_revision_number = 1

    def create_settings(self):
        self.image_name = ImageSubscriber(
            "Select the input image",
            "None",
            doc="""Select the image to be smoothed.""",
        )

        self.output_image_name = ImageName(
            "Name the output image",
            "FilteredImage",
            doc="""Enter a name for the resulting image.""",
        )

        self.calculate_maximal = Binary(
            "Calculate optimal window size to maximize image variance?",
            False,
            doc="""\
Select "*Yes*" to provide a range that will be used to obtain the window size that will generate
the maximum variance in the input image.
Select "*No*" to give the window size used to obtain the image variance.""",
        )

        self.window_size = Integer(
            "Window size",
            5,
            minval=1,
            doc="""Enter the size of the window used to calculate the variance.""",
        )

        self.window_min = Integer(
            "Window min",
            5,
            minval=1,
            doc="""Enter the minimum size of the window used to calculate the variance.""",
        )

        self.window_max = Integer(
            "Window max",
            50,
            minval=1,
            doc="""Enter the maximum size of the window used to calculate the variance.""",
        )

    def settings(self):
        return [
            self.image_name,
            self.output_image_name,
            self.calculate_maximal,
            self.window_size,
            self.window_min,
            self.window_max,
        ]

    def visible_settings(self):
        __settings__ = [
            self.image_name,
            self.output_image_name,
        ]
        __settings__ += [
            self.calculate_maximal,
        ]
        if not self.calculate_maximal.value:
            __settings__ += [
                self.window_size,
            ]
        else:
            __settings__ += [
                self.window_min,
                self.window_max,
            ]
        return __settings__

    def run(self, workspace):

        image = workspace.image_set.get_image(
            self.image_name.value, must_be_grayscale=True
        )

        image_pixels = image.pixel_data

        window_range = range(self.window_min.value, self.window_max.value, 1)

        size = self.window_size.value

        if self.calculate_maximal.value:
            max_variance = -1
            for window in window_range:
                result = abs(
                    scipy.ndimage.uniform_filter(
                        image_pixels**2, size=window, output=numpy.float64
                    )
                    - (
                        scipy.ndimage.uniform_filter(
                            image_pixels, size=window, output=numpy.float64
                        )
                        ** 2
                    )
                )
                variance = result.max()
                if variance > max_variance:
                    max_variance = variance
                    size = window

        output_pixels = abs(
            scipy.ndimage.uniform_filter(
                image_pixels**2, size=size, output=numpy.float64
            )
            - (
                scipy.ndimage.uniform_filter(
                    image_pixels, size=size, output=numpy.float64
                )
                ** 2
            )
        )

        new_image = Image(
            output_pixels, parent_image=image, dimensions=image.dimensions
        )

        workspace.image_set.add(self.output_image_name.value, new_image)

        if self.show_window:
            workspace.display_data.pixel_data = image_pixels

            workspace.display_data.output_pixels = output_pixels

            workspace.display_data.dimensions = image.dimensions

    def display(self, workspace, figure):
        layout = (2, 1)
        figure.set_subplots(
            dimensions=workspace.display_data.dimensions, subplots=layout
        )

        figure.subplot_imshow(
            colormap="gray",
            image=workspace.display_data.pixel_data,
            title=self.image_name.value,
            x=0,
            y=0,
        )

        figure.subplot_imshow(
            colormap="gray",
            image=workspace.display_data.output_pixels,
            title=self.output_image_name.value,
            x=1,
            y=0,
        )
