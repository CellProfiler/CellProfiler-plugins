#################################
#
# Imports from useful Python libraries
#
#################################
import numpy
import skimage.exposure

#################################
#
# Imports from CellProfiler
#
##################################

import cellprofiler_core.image
import cellprofiler_core.module
import cellprofiler_core.setting
import cellprofiler_core.setting.text
from cellprofiler_core.setting.subscriber import ImageSubscriber

__doc__ = """\
HistogramMatching 
================+
**HistogramMatching** manipulates the pixel intensity values an input image and matches
them to the histogram of a reference image. It can be used as a way to normalize intensities 
across different images or different frames of the same image. It allows you to choose 
which frame to use as the reference. 

|

============ ============ ===============
Supports 2D? Supports 3D? Respects masks?
============ ============ ===============
YES          YES          NO
============ ============ ===============

References
^^^^^^^^^^
(`link <http://paulbourke.net/miscellaneous/equalisation/>`__)
(`link <https://scikit-image.org/docs/stable/auto_examples/color_exposure/plot_histogram_matching.html>`__)
"""


class HistogramMatching(cellprofiler_core.module.ImageProcessing):
    module_name = "HistogramMatching"

    variable_revision_number = 1

    def create_settings(self):
        super(HistogramMatching, self).create_settings()

        self.reference_image = ImageSubscriber(
            "Image to use as reference ",
            doc="Select the image you want to use the reference.",
        )

        self.do_3D = cellprofiler_core.setting.Binary(
            text="Is your image 3D?",
            value=False,
            doc="""
            If enabled, 3D specific settings are available.""",
        )

        self.do_self_reference = cellprofiler_core.setting.Binary(
            text="Use a frame within image as reference?",
            value=False,
            doc="""
            If enabled, a frame within the 3D image is used as the reference image.""",
        )

        self.frame_number = cellprofiler_core.setting.text.Integer(
            "Frame number",
            value=5,
            minval=1,
            doc="""For 3D images, you have the option of performing histogram matching within the image using one of the frames in the image
                """,
        )

    def settings(self):
        __settings__ = super(HistogramMatching, self).settings()

        return __settings__ + [
            self.do_3D,
            self.do_self_reference,
            self.reference_image,
            self.frame_number,
        ]

    def visible_settings(self):
        __settings__ = super(HistogramMatching, self).settings()

        __settings__ += [self.do_3D, self.reference_image]

        if self.do_3D.value:
            __settings__ += [self.do_self_reference]

        if self.do_self_reference.value:
            __settings__.remove(self.reference_image)
            __settings__ += [self.frame_number]

        return __settings__

    def run(self, workspace):
        x_name = self.x_name.value

        y_name = self.y_name.value

        images = workspace.image_set

        x = images.get_image(x_name)

        dimensions = x.dimensions

        x_data = x.pixel_data

        if x.volumetric:
            y_data = numpy.zeros_like(x_data, dtype=numpy.float)

            if self.do_self_reference.value:
                reference_image = x_data[self.frame_number.value]
                for index, plane in enumerate(x_data):
                    y_data[index] = skimage.exposure.match_histograms(
                        plane, reference_image
                    )
            else:
                reference_image = images.get_image(self.reference_image)
                for index, plane in enumerate(x_data):
                    y_data = skimage.exposure.match_histograms(plane, reference_image)
        else:
            reference_image = images.get_image(self.reference_image).pixel_data
            y_data = skimage.exposure.match_histograms(x_data, reference_image)

        y = cellprofiler_core.image.Image(
            dimensions=dimensions, image=y_data, parent_image=x
        )

        images.add(y_name, y)

        if self.show_window:
            workspace.display_data.x_data = x_data

            workspace.display_data.y_data = y_data

            workspace.display_data.dimensions = dimensions
