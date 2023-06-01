# coding=utf-8

"""
ConvertOutlinesToObjects
=====================

**ConvertOutlinesToObjects** converts a binary image of outlines to objects. Contiguous outlined regions are converted
to unique objects.

|

============ ============ ===============
Supports 2D? Supports 3D? Respects masks?
============ ============ ===============
YES          YES          NO
============ ============ ===============
"""

import numpy
import scipy.ndimage
import skimage
import skimage.measure

import cellprofiler.module
import cellprofiler.setting


class ConvertOutlinesToObjects(cellprofiler.module.ImageSegmentation):
    category = "Advanced"

    module_name = "ConvertOutlinesToObjects"

    variable_revision_number = 1

    def create_settings(self):
        super(ConvertOutlinesToObjects, self).create_settings()

        self.diameter = cellprofiler.setting.FloatRange(
            text="Typical diameter of objects",
            value=(0.0, numpy.inf),
            doc="Typical diameter of objects, in pixels (min, max). Objects outside this range will be discarded."
        )

    def settings(self):
        settings = super(ConvertOutlinesToObjects, self).settings()

        settings += [
            self.diameter
        ]

        return settings

    def visible_settings(self):
        visible_settings = super(ConvertOutlinesToObjects, self).visible_settings()

        visible_settings += [
            self.diameter
        ]

        return visible_settings

    def run(self, workspace):
        self.function = convert_outlines_to_objects

        super(ConvertOutlinesToObjects, self).run(workspace)


def convert_outlines_to_objects(outlines, diameter):
    labels = skimage.measure.label(
        outlines > 0,
        background=True,
        connectivity=1
    )

    indexes = numpy.unique(labels)

    radius = numpy.divide(diameter, 2.0)

    if labels.ndim == 2:
        factor = radius ** 2
    else:
        factor = (4.0 / 3.0) * (radius ** 3)

    min_area, max_area = numpy.pi * factor

    areas = scipy.ndimage.sum(
        numpy.ones_like(labels),
        labels,
        index=indexes
    )

    is_background = numpy.logical_or(
        areas < min_area,
        areas > max_area
    )

    background_indexes = numpy.unique(labels)[is_background]

    labels[numpy.isin(labels, background_indexes)] = 0

    return labels
