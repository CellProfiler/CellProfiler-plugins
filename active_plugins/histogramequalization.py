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
HistogramEqualization 
=====================
**HistogramEqualization** increases the global contrast of 
a low-contrast image or volume. Histogram equalization redistributes intensities 
to utilize the full range of intensities, such that the most common frequencies 
are more distinct.

|

============ ============ ===============
Supports 2D? Supports 3D? Respects masks?
============ ============ ===============
YES          YES          YES
============ ============ ===============

Technical notes
^^^^^^^^^^^^^^^
This module can perform two types of histogram equalization; a global method (HE) and 
a local method (Adaptive Histogram Equalization - AHE). A local method might perform 
better in some cases but it might increase the background noise. The clipping limit 
setting can help limit noise amplification (Contrast Limited AHE - CLAHE). 
Look at the references for more information.

References
^^^^^^^^^^
(`link <http://www.janeriksolem.net/histogram-equalization-with-python-and.html>`__)
(`link <https://docs.opencv.org/3.1.0/d5/daf/tutorial_py_histogram_equalization.html>`__)
"""


class HistogramEqualization(cellprofiler_core.module.ImageProcessing):
    module_name = "HistogramEqualization"

    variable_revision_number = 1

    def create_settings(self):
        super(HistogramEqualization, self).create_settings()

        self.nbins = cellprofiler_core.setting.text.Integer(
            "Bins", value=256, minval=0, doc="Number of bins for image histogram."
        )

        self.tile_size = cellprofiler_core.setting.text.Integer(
            "Tile Size",
            value=50,
            minval=1,
            doc="""The image is partitioned into tiles of the specified size. Choose a tile size that will fit at least one object of interest.
            """,
        )

        self.mask = ImageSubscriber(
            "Mask",
            can_be_blank=True,
            doc="""
            Optional. Mask image must be the same size as "Input". Only unmasked points of the "Input" image are used
            to compute the equalization, which is applied to the entire "Input" image.
            """,
        )

        self.local = cellprofiler_core.setting.Binary("Local", False)

        self.clip_limit = cellprofiler_core.setting.text.Float(
            "Clip limit",
            value=0.01,
            minval=0,
            maxval=1,
            doc="""Normalized between 0 and 1. Higher values give more contrast but will also result in over-amplification of background in areas of low or no signal.
            """,
        )

        self.do_3D = cellprofiler_core.setting.Binary(
            text="Is your image 3D?",
            value=False,
            doc="""
            If enabled, 3D specific settings will be available.""",
        )

        self.do_framewise = cellprofiler_core.setting.Binary(
            text="Do framewise calculation?",
            value=False,
            doc="""
            If enabled, the histogram equalization will be calculated frame-wise instead of using the image volume""",
        )

        self.tile_z_size = cellprofiler_core.setting.text.Integer(
            "Tile Size (Z)",
            value=5,
            minval=1,
            doc="""For 3D image you have the option of performing histogram equalization one z-frame at a time or using a 3D tile
                """,
        )

    def settings(self):
        __settings__ = super(HistogramEqualization, self).settings()

        return __settings__ + [
            self.nbins,
            self.mask,
            self.local,
            self.tile_size,
            self.clip_limit,
            self.do_3D,
            self.do_framewise,
            self.tile_z_size,
        ]

    def visible_settings(self):
        __settings__ = super(HistogramEqualization, self).settings()

        __settings__ += [self.local, self.nbins, self.do_3D]

        if not self.local.value:
            __settings__ += [self.mask]
            if self.do_3D.value:
                __settings__ += [self.do_framewise]
        else:
            __settings__ += [
                self.clip_limit,
                self.tile_size,
            ]
            if self.do_3D.value:
                __settings__ += [self.do_framewise]
                if not self.do_framewise.value:
                    __settings__ += [self.tile_z_size]
        return __settings__

    def run(self, workspace):
        x_name = self.x_name.value

        y_name = self.y_name.value

        images = workspace.image_set

        x = images.get_image(x_name)

        dimensions = x.dimensions

        x_data = x.pixel_data

        mask_data = None

        if not self.mask.is_blank:
            mask_name = self.mask.value

            mask = images.get_image(mask_name)

            mask_data = mask.pixel_data

        nbins = self.nbins.value

        if self.local.value:

            kernel_size = self.tile_size.value
            clip_limit = self.clip_limit.value

            if self.do_3D.value:
                y_data = numpy.zeros_like(x_data, dtype=numpy.float)
                if self.do_framewise.value:
                    for index, plane in enumerate(x_data):
                        y_data[index] = skimage.exposure.equalize_adapthist(
                            plane,
                            kernel_size=kernel_size,
                            nbins=nbins,
                            clip_limit=clip_limit,
                        )
                else:
                    kernel_size = (
                        self.tile_z_size.value,
                        self.tile_size.value,
                        self.tile_size.value,
                    )
                    y_data = skimage.exposure.equalize_adapthist(
                        x_data,
                        kernel_size=kernel_size,
                        nbins=nbins,
                        clip_limit=clip_limit,
                    )
            else:
                y_data = skimage.exposure.equalize_adapthist(
                    x_data, kernel_size=kernel_size, nbins=nbins, clip_limit=clip_limit
                )
        else:
            if self.do_3D.value:
                y_data = numpy.zeros_like(x_data, dtype=numpy.float)
                if self.do_framewise.value:
                    for index, plane in enumerate(x_data):
                        y_data[index] = skimage.exposure.equalize_hist(
                            plane, nbins=nbins, mask=mask_data
                        )
                else:
                    y_data = skimage.exposure.equalize_hist(
                        x_data, nbins=nbins, mask=mask_data
                    )
            else:
                y_data = skimage.exposure.equalize_hist(
                    x_data, nbins=nbins, mask=mask_data
                )

        y = cellprofiler_core.image.Image(
            dimensions=dimensions, image=y_data, parent_image=x
        )

        images.add(y_name, y)

        if self.show_window:
            workspace.display_data.x_data = x_data

            workspace.display_data.y_data = y_data

            workspace.display_data.dimensions = dimensions
