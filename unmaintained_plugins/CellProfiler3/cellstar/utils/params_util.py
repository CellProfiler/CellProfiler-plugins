# -*- coding: utf-8 -*-
"""
Params util module contains methods for manipulating parameters and precision to parameters mapping
Date: 2013-2016
Website: http://cellstar-algorithm.org/
"""

import numpy as np

from cellstar.core.config import default_config


def default_parameters(segmentation_precision=-1, avg_cell_diameter=-1):
    parameters = default_config()
    if avg_cell_diameter != -1:
        parameters["segmentation"]["avgCellDiameter"] = avg_cell_diameter

    if segmentation_precision is None:
        return parameters
    else:
        return parameters_from_segmentation_precision(parameters, segmentation_precision)


def create_size_weights(size_weight_average, length):
    if length == 1:
        size_weight_multiplier = np.array([1])
    elif length == 2:
        size_weight_multiplier = np.array([0.8, 1.25])
    elif length == 3:
        size_weight_multiplier = np.array([0.6, 1, 1.6])
    elif length == 4:
        size_weight_multiplier = np.array([0.5, 0.8, 1.3, 2])
    elif length == 5:
        size_weight_multiplier = np.array([0.5, 0.8, 1, 1.3, 2])
    elif length == 6:
        size_weight_multiplier = np.array([0.35, 0.5, 0.8, 1.3, 2, 3])
    else:
        size_weight_multiplier = np.array([0.25, 0.35, 0.5, 0.8, 1.3, 2, 3, 5, 8])

    return size_weight_average * size_weight_multiplier / np.average(size_weight_multiplier)


def parameters_from_segmentation_precision(parameters, segmentation_precision):
    sfrom = lambda x: max(0, segmentation_precision - x)
    segmentation_precision = min(20, segmentation_precision)
    if segmentation_precision <= 0:
        parameters["segmentation"]["steps"] = 0
    elif segmentation_precision <= 6:
        parameters["segmentation"]["steps"] = 1
    else:
        parameters["segmentation"]["steps"] = min(10, segmentation_precision - 5)

    parameters["segmentation"]["stars"]["points"] = 8 + max(segmentation_precision - 2, 0) * 4

    parameters["segmentation"]["maxFreeBorder"] = \
        max(0.4, 0.7 * 16 / max(16, parameters["segmentation"]["stars"]["points"]))

    parameters["segmentation"]["seeding"]["from"]["cellBorder"] = int(segmentation_precision >= 2)
    parameters["segmentation"]["seeding"]["from"]["cellBorderRandom"] = sfrom(14)
    parameters["segmentation"]["seeding"]["from"]["cellContent"] = int(segmentation_precision >= 11)
    parameters["segmentation"]["seeding"]["from"]["cellContentRandom"] = min(4, sfrom(12))
    parameters["segmentation"]["seeding"]["from"]["cellBorderRemovingCurrSegments"] = \
        int(segmentation_precision >= 11)
    parameters["segmentation"]["seeding"]["from"]["cellBorderRemovingCurrSegmentsRandom"] = max(0, min(4, sfrom(16)))
    parameters["segmentation"]["seeding"]["from"]["cellContentRemovingCurrSegments"] = \
        int(segmentation_precision >= 7)
    parameters["segmentation"]["seeding"]["from"]["cellContentRemovingCurrSegmentsRandom"] = max(0, min(4, sfrom(12)))
    parameters["segmentation"]["seeding"]["from"]["snakesCentroids"] = int(segmentation_precision >= 9)
    parameters["segmentation"]["seeding"]["from"]["snakesCentroidsRandom"] = max(0, min(4, sfrom(14)))

    parameters["segmentation"]["stars"]["step"] = 0.0067 * max(1, (1 + (15 - segmentation_precision) / 2.0))

    if segmentation_precision <= 9:
        weight_length = 1
    elif segmentation_precision <= 11:
        weight_length = 2
    elif segmentation_precision <= 13:
        weight_length = 3
    elif segmentation_precision <= 15:
        weight_length = 4
    elif segmentation_precision <= 17:
        weight_length = 6
    else:
        weight_length = 9

    parameters["segmentation"]["stars"]["sizeWeight"] = list(
        create_size_weights(np.average(parameters["segmentation"]["stars"]["sizeWeight"]), weight_length)
    )

    parameters["segmentation"]["foreground"]["pickyDetection"] = segmentation_precision > 8

    return parameters
