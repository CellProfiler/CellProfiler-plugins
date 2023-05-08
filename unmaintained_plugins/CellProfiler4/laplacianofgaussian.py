# coding=utf-8

"""
Laplacian of Gaussian filter.
"""

import cellprofiler_core.image
import cellprofiler_core.module
import cellprofiler_core.setting
import cellprofiler_core.setting.text
import scipy.ndimage.filters
import skimage.color


class LaplacianOfGaussian(cellprofiler_core.module.ImageProcessing):
    module_name = "LaplacianOfGaussian"

    variable_revision_number = 1

    def create_settings(self):
        super(LaplacianOfGaussian, self).create_settings()

        self.x = cellprofiler_core.setting.text.Float(
            "Sigma x",
            value=1.0,
            minval=0.0,
            doc="Sigma for x axis."
        )

        self.y = cellprofiler_core.setting.text.Float(
            "Sigma y",
            value=1.0,
            minval=0.0,
            doc="Sigma for y axis."
        )

        self.z = cellprofiler_core.setting.text.Float(
            "Sigma z",
            value=1.0,
            minval=0.0,
            doc="Sigma for z axis. Ignored when input is a two-dimensional image."
        )

    def settings(self):
        __settings__ = super(LaplacianOfGaussian, self).settings()

        return __settings__ + [
            self.x,
            self.y,
            self.z
        ]

    def visible_settings(self):
        __settings__ = super(LaplacianOfGaussian, self).visible_settings()

        return __settings__ + [
            self.x,
            self.y,
            self.z
        ]

    def run(self, workspace):
        x_name = self.x_name.value

        y_name = self.y_name.value

        images = workspace.image_set

        x = images.get_image(x_name)

        x_data = x.pixel_data

        if x.multichannel:
            x_data = skimage.color.rgb2gray(x_data)

        x_data = skimage.img_as_float(x_data)

        dimensions = x.dimensions

        if dimensions == 2:
            sigma = (self.x.value, self.y.value)
        else:
            sigma = (self.z.value, self.x.value, self.y.value)

        y_data = scipy.ndimage.filters.gaussian_laplace(x_data, sigma)

        y = cellprofiler_core.image.Image(
            dimensions=dimensions,
            image=y_data,
            parent_image=x
        )

        images.add(y_name, y)

        if self.show_window:
            workspace.display_data.x_data = x_data

            workspace.display_data.y_data = y_data

            workspace.display_data.dimensions = dimensions
