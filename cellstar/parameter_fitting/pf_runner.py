# -*- coding: utf-8 -*-
"""
Entry point for running fitting process both parameter sets: contour and ranking.
Date: 2013-2016
Website: http://cellstar-algorithm.org/
"""
import logging

import sys
import numpy as np
import scipy as sp

import cellstar.parameter_fitting.pf_process as pf_process
import cellstar.parameter_fitting.pf_rank_process as pf_rank
from cellstar.parameter_fitting.pf_snake import GTSnake

try:
    from cellprofiler.preferences import get_max_workers
except:
    get_max_workers = lambda: 1
    
logger = logging.getLogger(__name__)


def single_mask_to_snake(bool_mask, seed=None):
    return GTSnake(bool_mask, seed)


def gt_label_to_snakes(components):
    num_components = components.max()
    return [single_mask_to_snake(components == label) for label in range(1, num_components + 1)]


def image_to_label(image):
    values = np.unique(image)
    if len(values) == 2:  # it is a mask
        components, num_components = sp.ndimage.label(image, np.ones((3, 3)))
        return components
    else:  # remap labels to [1..] values
        curr = 1
        label_image = image.copy()
        for v in values[1:]:  # zero is ignored
            label_image[image == v] = curr
            curr += 1
        return label_image


def run_pf(input_image, background_image, ignore_mask_image, gt_label, parameters, precision, avg_cell_diameter,
           callback_progress=None):
    """
    :param input_image:
    :param gt_label:
    :param parameters:
    :return: Best complete parameters settings, best distance
    """

    gt_mask = image_to_label(gt_label)
    pf_process.callback_progress = callback_progress

    gt_snakes = gt_label_to_snakes(gt_mask)
    if get_max_workers() > 1:
        best_complete_params, _, best_score = pf_process.run(input_image, gt_snakes, precision=precision,
                                                  avg_cell_diameter=avg_cell_diameter, initial_params=parameters,
                                                  method='mp', background_image=background_image,
                                                  ignore_mask=ignore_mask_image)
    else:
        best_complete_params, _, best_score = pf_process.run(input_image, gt_snakes, precision=precision,
                                                  avg_cell_diameter=avg_cell_diameter, initial_params=parameters,
                                                  method='brutemaxbasin', background_image=background_image,
                                                  ignore_mask=ignore_mask_image)

    return best_complete_params, best_score


def run_rank_pf(input_image, background_image, ignore_mask_image, gt_mask, parameters, callback_progress=None):
    """
    :return: Best complete parameters settings, best distance
    """

    gt_mask = image_to_label(gt_mask)
    pf_rank.callback_progress = callback_progress

    gt_snakes = gt_label_to_snakes(gt_mask)
    if get_max_workers() > 1 and not (getattr(sys, "frozen", False) and sys.platform == 'win32'):
        # multiprocessing do not work if frozen on win32
        best_complete_params, _, best_score = pf_rank.run_multiprocess(input_image, gt_snakes,
                                                                       initial_params=parameters,
                                                                       method='brutemaxbasin',
                                                                       background_image=background_image,
                                                                       ignore_mask=ignore_mask_image)
    else:
        best_complete_params, _, best_score = pf_rank.run_singleprocess(input_image, gt_snakes,
                                                                        initial_params=parameters,
                                                                        method='brutemaxbasin',
                                                                        background_image=background_image,
                                                                        ignore_mask=ignore_mask_image)

    return best_complete_params, best_score