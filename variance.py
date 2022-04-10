"""
Variance
======

**Variance** 

This module allows you to calculate the variance of an image, using a determined window size.

|

============ ============ ===============
Supports 2D? Supports 3D? Respects masks?
============ ============ ===============
YES          NO           NO
============ ============ ===============

"""

import numpy
import scipy.ndimage
import skimage.restoration

from cellprofiler_core.image import Image
from cellprofiler_core.module import Module
from cellprofiler_core.setting import Binary
from cellprofiler_core.setting.choice import Choice
from cellprofiler_core.setting.subscriber import ImageSubscriber
from cellprofiler_core.setting.text import ImageName, Float, Integer
from centrosome.filter import median_filter, circular_average_filter
from centrosome.smooth import fit_polynomial
from centrosome.smooth import smooth_with_function_and_mask

class Variance(Module):
    module_name = "Variance"
    category = "Image Processing"
    variable_revision_number = 1

    def create_settings(self):
        self.image_name = ImageSubscriber(
            "Select the input image",
            "None",
            doc="""Select the image to be smoothed.""",
        )

        self.output_image_name = ImageName(
            "Name the output image",
            "VarianceImage",
            doc="""Enter a name for the resulting image.""",
        )

        self.window_size = Integer(
            "Window size",
            5, 
            minval=1,
            doc="""Enter the size of the window used to calculate the variance.""",
        )

    def settings(self):
        return [
            self.image_name,
            self.output_image_name,
            self.window_size,
        ]

    def visible_settings(self):
        result = [self.image_name, self.output_image_name, self.window_size]
        return result

    def run(self, workspace):
        image = workspace.image_set.get_image(self.image_name.value, must_be_grayscale=True)
        
        image_pixels = image.pixel_data

        output_pixels = scipy.ndimage.uniform_filter(image_pixels**2, size=self.window_size.value, output=numpy.float64) 
        - (scipy.ndimage.uniform_filter(image_pixels, size=self.window_size.value, output=numpy.float64)**2)

        new_image = Image(output_pixels, parent_image=image, dimensions=image.dimensions)
        
        workspace.image_set.add(self.output_image_name.value, new_image)
        if self.show_window:
            workspace.display_data.pixel_data  = image_pixels

            workspace.display_data.output_pixels= output_pixels

            workspace.display_data.dimensions = image.dimensions

    def display(self, workspace, figure):
        image = workspace.display_data.pixel_data
        output_pixels = workspace.display_data.output_pixels
        
        figure.set_subplots((2, 1))
        
        figure.subplot_imshow_grayscale(
                0, 
                0, 
                image, 
                "Original image: %s" % self.image_name.value
            )
        figure.subplot_imshow_grayscale(
                1,
                0,
                output_pixels,
                self.output_image_name.value,
            )
