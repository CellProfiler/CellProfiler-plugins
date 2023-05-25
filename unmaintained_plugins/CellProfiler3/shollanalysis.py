# coding=utf-8

"""
ShollAnalysis
====================

|

============ ============ ===============
Supports 2D? Supports 3D? Respects masks?
============ ============ ===============
YES          YES          YES
============ ============ ===============

Measurements made by this module
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- *Branches*: Total number of pixels with more than two neighbors.

- *Endpoints*: Total number of pixels with only one neighbor.
"""

import numpy
import scipy.ndimage
import skimage.draw
import skimage.segmentation
import skimage.util

import cellprofiler.measurement
import cellprofiler.module
import cellprofiler.setting


def sholl(image, radius, step):
    r_radius = radius
    c_radius = radius

    r, c = image.shape

    centroid_r, centroid_c = r // 2, c // 2

    shells = numpy.minimum(
        centroid_r // (step + 1),
        centroid_c // (step + 1)
    )

    masks = numpy.zeros((shells, r, c))

    for index in range(shells):
        if index == 0:
            next_step = 0

        previous_shell_rr, previous_shell_cc = skimage.draw.ellipse(
            centroid_r,
            centroid_c,
            r_radius + next_step,
            c_radius + next_step
        )

        next_step += step

        shell_rr, shell_cc = skimage.draw.ellipse(
            centroid_r,
            centroid_c,
            r_radius + next_step,
            c_radius + next_step
        )

        masks[index, shell_rr, shell_cc] = 1

        masks[index, previous_shell_rr, previous_shell_cc] = 0

    neighborhoods = numpy.zeros((shells, r, c))

    for index in range(shells):
        neighborhoods[index] = image * masks[index]

    return neighborhoods


def _neighbors(image):
    """

    Counts the neighbor pixels for each pixel of an image:

            x = [
                [0, 1, 0],
                [1, 1, 1],
                [0, 1, 0]
            ]

            _neighbors(x)

            [
                [0, 3, 0],
                [3, 4, 3],
                [0, 3, 0]
            ]

    :type image: numpy.ndarray

    :param image: A two-or-three dimensional image

    :return: neighbor pixels for each pixel of an image

    """
    padding = skimage.util.pad(image, 1, "constant")

    mask = padding > 0

    padding = padding.astype(numpy.float)

    if image.ndim == 2:
        response = 3 ** 2 * scipy.ndimage.uniform_filter(padding) - 1

        labels = (response * mask)[1:-1, 1:-1]

        return labels.astype(numpy.uint16)
    elif image.ndim == 3:
        response = 3 ** 3 * scipy.ndimage.uniform_filter(padding) - 1

        labels = (response * mask)[1:-1, 1:-1, 1:-1]

        return labels.astype(numpy.uint16)


def branches(image):
    return _neighbors(image) > 2


def endpoints(image):
    return _neighbors(image) == 1


class ShollAnalysis(cellprofiler.module.Module):
    category = "Measurement"

    module_name = "ShollAnalysis"

    variable_revision_number = 1

    def create_settings(self):
        self.skeleton_name = cellprofiler.setting.ImageNameSubscriber(
            "Select an image to measure"
        )

        self.radius = cellprofiler.setting.Integer(
            "Radius"
        )

        self.step = cellprofiler.setting.Integer(
            "Step"
        )

    def settings(self):
        return [
            self.skeleton_name,
            self.radius,
            self.step
        ]

    def run(self, workspace):
        names = []

        input_image_name = self.skeleton_name.value

        image_set = workspace.image_set

        input_image = image_set.get_image(input_image_name, must_be_grayscale=True)

        dimensions = input_image.dimensions

        r_radius = self.radius.value
        c_radius = self.radius.value

        r, c = input_image.pixel_data.shape

        centroid_r, centroid_c = r // 2, c // 2

        shells = numpy.minimum(
            centroid_r // (self.step.value + 1),
            centroid_c // (self.step.value + 1)
        )

        masks = numpy.zeros((shells, r, c))

        for index in range(shells):
            if index == 0:
                next_step = 0

            previous_shell_rr, previous_shell_cc = skimage.draw.ellipse(
                centroid_r,
                centroid_c,
                r_radius + next_step,
                c_radius + next_step
            )

            next_step += self.step.value

            shell_rr, shell_cc = skimage.draw.ellipse(
                centroid_r,
                centroid_c,
                r_radius + next_step,
                c_radius + next_step
            )

            masks[index, shell_rr, shell_cc] = 1

            masks[index, previous_shell_rr, previous_shell_cc] = 0

        neighborhoods = numpy.zeros((shells, r, c))

        for index in range(shells):
            neighborhoods[index] = input_image.pixel_data * masks[index]

            names.append("Branches_{}".format(index))

            names.append("Endpoints_{}".format(index))

        self.neighborhoods = neighborhoods

        statistics = self.measure(input_image, workspace)

        if self.show_window:
            workspace.display_data.dimensions = dimensions

            workspace.display_data.names = names

            workspace.display_data.statistics = statistics

    def display(self, workspace, figure=None):
        layout = (1, 1)

        figure.set_subplots(
            dimensions=workspace.display_data.dimensions,
            subplots=layout
        )

        figure.subplot_table(
            col_labels=workspace.display_data.names,
            statistics=workspace.display_data.statistics,
            title="Measurement",
            x=0,
            y=0
        )

    def get_categories(self, pipeline, object_name):
        if object_name == cellprofiler.measurement.IMAGE:
            return [
                "Skeleton"
            ]

        return []

    def get_feature_name(self, name):
        image = self.skeleton_name.value

        return "ShollAnalysis_{}_{}".format(image, name)

    def get_measurements(self, pipeline, object_name, category):
        name = self.skeleton_name.value

        if object_name == cellprofiler.measurement.IMAGE and category == "Skeleton":
            return [
                "ShollAnalysis_Branches_{}".format(name),
                "ShollAnalysis_Endpoints_{}".format(name)
            ]

        return []

    def get_measurement_columns(self, pipeline):
        image = cellprofiler.measurement.IMAGE

        features = [
            self.get_measurement_name("Branches"),
            self.get_measurement_name("Endpoints")
        ]

        column_type = cellprofiler.measurement.COLTYPE_INTEGER

        return [(image, feature, column_type) for feature in features]

    def get_measurement_images(self, pipeline, object_name, category, measurement):
        if measurement in self.get_measurements(pipeline, object_name, category):
            return [self.skeleton_name.value]

        return []

    def get_measurement_name(self, name):
        feature = self.get_feature_name(name)

        return feature

    def measure(self, image, workspace):
        image = image.pixel_data

        data = sholl(image, self.radius.value, self.step.value)

        measurements = workspace.measurements

        measurement_name = self.skeleton_name.value

        statistics = []

        for index in range(self.neighborhoods.shape[0]):
            name = "ShollAnalysis_Branches_{}_{}".format(measurement_name, index)

            value = numpy.count_nonzero(branches(data))

            statistics.append(value)

            measurements.add_image_measurement(name, value)

            name = "ShollAnalysis_Endpoints_{}_{}".format(measurement_name, index)

            value = numpy.count_nonzero(endpoints(data))

            statistics.append(value)

            measurements.add_image_measurement(name, value)

        return [statistics]

    def volumetric(self):
        return True
