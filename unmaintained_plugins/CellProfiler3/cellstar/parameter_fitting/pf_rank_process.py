# -*- coding: utf-8 -*-
"""
Pf rank process is the core of ranking parameters fitting.
Date: 2013-2016
Website: http://cellstar-algorithm.org/
"""

import operator as op
import random
import time

import numpy as np
import scipy.optimize as opt
from scipy.linalg import norm

random.seed(1)
np.random.seed(1)

import logging

logger = logging.getLogger(__name__)

from cellstar.utils.params_util import *
from cellstar.core.image_repo import ImageRepo
from cellstar.core.snake_filter import SnakeFilter
from cellstar.utils.debug_util import explore_cellstar
from cellstar.parameter_fitting.pf_process import get_gt_snake_seeds, grow_single_seed, \
    general_multiproc_fitting
from cellstar.parameter_fitting.pf_rank_snake import PFRankSnake
from cellstar.parameter_fitting.pf_auto_params import pf_parameters_encode, pf_rank_parameters_encode, \
    pf_rank_parameters_decode, RankBounds
from cellstar.parameter_fitting.pf_mutator import *

#
#
# PROGRESS CALLBACKS
#
#
ESTIMATED_CALCULATIONS_NUMBER = 20000.0
callback_progress = None


def show_progress(current_distance, calculation):
    if calculations % 100 == 0:
        logger.debug("Rank current: %f, Best: %f, Calc %d" % (current_distance, best_so_far, calculation))
    if callback_progress is not None and calculation % (ESTIMATED_CALCULATIONS_NUMBER / 50) == 0:
        callback_progress(float(calculation) / ESTIMATED_CALCULATIONS_NUMBER)

#
#
# COST FUNCTION AND FITNESS
#
#

best_so_far = 1000000000
calculations = 0


def maximal_distance(n):
    l = n - 1
    return l * (l + 1) * (l + 2) / 6.0 * 2


def distance_smooth_norm(expected, result):
    """
    Calculates 2-norm from difference in fitness between expected and given snakes
    @param expected: array of expected fitness
    @param result: array of given fitness
    @return:
    """
    global best_so_far, calculations
    n = result.size
    differences = abs(expected - result) ** 4 * np.arange(n * 2, 0, -2)
    distance = norm(differences) / np.sqrt(n)

    best_so_far = min(best_so_far, distance)
    calculations += 1

    show_progress(distance, calculations)
    return distance


def distance_norm_list(expected, result):
    """
    Calculates number of derangments between two sequences
    @param expected: expected order
    @param result: given order
    @return:
    """
    global best_so_far, calculations
    length = len(expected)
    exp_position = dict([(obj, i) for (i, obj) in enumerate(expected)])
    given_position = dict([(obj, i) for (i, obj) in enumerate(result)])
    positions = enumerate(result)
    distance = sum(
        [abs(exp_position[obj] - i) ** 2 / (exp_position[obj] + 1) ** 2 for (i, obj) in positions]) / maximal_distance(
        length)  # scaling to [0,1]

    best_so_far = min(best_so_far, distance)
    calculations += 1

    show_progress(distance, calculations)
    return distance


def calc_ranking(rank_snakes, pf_param_vector):
    rank_params_decoded = pf_rank_parameters_decode(pf_param_vector)
    fitness_order = sorted(rank_snakes, key=lambda x: -x.fitness)
    ranking_order = sorted(rank_snakes, key=lambda x: x.calculate_ranking(rank_params_decoded))
    return distance_norm_list(fitness_order, ranking_order)


def calc_smooth_ranking(rank_snakes, pf_param_vector):
    rank_params_decoded = pf_rank_parameters_decode(pf_param_vector)
    fitness_order = np.array([r.fitness for r in sorted(rank_snakes, key=lambda x: -x.fitness)])
    ranking_order = np.array(
        [r.fitness for r in sorted(rank_snakes, key=lambda x: x.calculate_ranking(rank_params_decoded))])
    return distance_smooth_norm(fitness_order, ranking_order)


def pf_rank_get_ranking(rank_snakes, initial_parameters):
    fitness = lambda partial_parameters, debug=False: \
        calc_smooth_ranking(
            rank_snakes,
            partial_parameters
        )

    return fitness


def filter_snakes_as_singles(parameters, images, snakes):
    """
    @type snakes: list[(GTSnake, PFRankSnake)]
    """
    filterer = SnakeFilter(images, parameters)
    proper_snakes = [(gt, snake) for gt, snake in snakes if not filterer.is_single_snake_discarded(snake.grown_snake)]
    logger.debug("Filtering left %d out of %d rank snakes" % (len(snakes) - len(proper_snakes), len(snakes)))
    return proper_snakes


#
#
# OPTIMIZATION
#
#

def run_multiprocess(image, gt_snakes, precision=None, avg_cell_diameter=None, method='brute', initial_params=None,
                     background_image=None, ignore_mask=None):
    """
    :param gt_snakes: gt snakes label image
    :param precision: if initial_params is None then it is used to calculate parameters
    :param avg_cell_diameter: if initial_params is None then it is used to calculate parameters
    :param method: optimization engine
    :param initial_params: overrides precision and avg_cell_diameter
    :return:
    """
    logger.info("Ranking parameter fitting (mp) started...")

    if initial_params is None:
        params = default_parameters(segmentation_precision=precision, avg_cell_diameter=avg_cell_diameter)
    else:
        params = copy.deepcopy(initial_params)
        avg_cell_diameter = params["segmentation"]["avgCellDiameter"]

    start = time.clock()
    best_params, distance = multiproc_optimize((image, background_image, ignore_mask), gt_snakes, method, params)
    best_params_full = PFRankSnake.merge_rank_parameters(params, best_params)
    stop = time.clock()

    logger.debug("Best: \n" + "\n".join([k + ": " + str(v) for k, v in sorted(best_params.iteritems())]))
    logger.debug("Time: %d" % (stop - start))
    logger.info("Ranking parameter fitting (mp) finished with best score %f" % distance)
    return best_params_full, best_params, distance


def run_singleprocess(image, gt_snakes, precision=None, avg_cell_diameter=None, method='brute', initial_params=None,
                      background_image=None, ignore_mask=None):
    """
    :param gt_snakes: gt snakes label image
    :param precision: if initial_params is None then it is used to calculate parameters
    :param avg_cell_diameter: if initial_params is None then it is used to calculate parameters
    :param method: optimization engine
    :param initial_params: overrides precision and avg_cell_diameter
    :return:
    """
    global calculations
    logger.info("Ranking parameter fitting started...")

    if initial_params is None:
        params = default_parameters(segmentation_precision=precision, avg_cell_diameter=avg_cell_diameter)
    else:
        params = copy.deepcopy(initial_params)
        avg_cell_diameter = params["segmentation"]["avgCellDiameter"]

    start = time.clock()

    images = ImageRepo(image, params)
    images.background = background_image
    if ignore_mask is not None:
        images.apply_mask(ignore_mask)

    # prepare seed and grow snakes
    encoded_star_params = pf_parameters_encode(params)
    radius = params["segmentation"]["seeding"]["randomDiskRadius"] * params["segmentation"]["avgCellDiameter"]
    radius_big = params["segmentation"]["avgCellDiameter"] * 1.5
    gt_snake_seed_pairs = [(gt_snake, seed) for gt_snake in gt_snakes for seed in
                           get_gt_snake_seeds(gt_snake, max_radius=radius, number=8, min_radius=2 * radius / 3.0)
                           + get_gt_snake_seeds(gt_snake, max_radius=radius, number=8, min_radius=4 * radius / 5.0)
                           + get_gt_snake_seeds(gt_snake, max_radius=radius_big, number=8,
                                                min_radius=3 * radius_big / 4.0)
                           ]

    gt_snake_grown_seed_pairs = \
        [(gt_snake, grow_single_seed(seed, images, params, encoded_star_params)) for gt_snake, seed in
         gt_snake_seed_pairs]

    gt_snake_grown_seed_pairs_all = reduce(op.add,
                                           [PFRankSnake.create_all(gt, grown, params) for (gt, grown) in
                                            gt_snake_grown_seed_pairs])

    # gt_snake_grown_seed_pairs_filtered = filter_snakes_as_singles(params, images, gt_snake_grown_seed_pairs_all)
    gt_snake_grown_seed_pairs_filtered = gt_snake_grown_seed_pairs_all

    # gts_snakes_with_mutations = add_mutations(gt_snake_grown_seed_pairs_all, avg_cell_diameter)
    gts_snakes_with_mutations = gt_snake_grown_seed_pairs_filtered
    ranked_snakes = zip(*gts_snakes_with_mutations)[1]

    explore_cellstar(image=images.image, images=images, params=params,
                     seeds=[sp[1].grown_snake.seed for sp in gts_snakes_with_mutations],
                     snakes=[sp[1].grown_snake for sp in gts_snakes_with_mutations])

    calculations = 0
    best_params_encoded, distance = optimize(
        method,
        pf_rank_parameters_encode(params),
        pf_rank_get_ranking(ranked_snakes, params)
    )

    stop = time.clock()

    best_params_org = pf_rank_parameters_decode(best_params_encoded)
    best_params_full = PFRankSnake.merge_rank_parameters(params, best_params_org)

    explore_cellstar(image=images.image, images=images, params=best_params_full,
                     seeds=[sp[1].grown_snake.seed for sp in gts_snakes_with_mutations],
                     snakes=[sp[1].grown_snake for sp in gts_snakes_with_mutations])

    logger.debug("Best: \n" + "\n".join([k + ": " + str(v) for k, v in sorted(best_params_org.iteritems())]))
    logger.debug("Time: %d" % (stop - start))
    logger.info("Ranking parameter fitting finished with best score %f" % distance)
    return best_params_full, best_params_org, distance


#
#
#   OPTIMISATION METHODS
#
#

def optimize(method_name, encoded_params, distance_function):
    initial_distance = distance_function(encoded_params)
    logger.debug("Initial parameters distance is (%f)." % initial_distance)
    if method_name == 'brute':
        best_params_encoded, distance = optimize_brute(encoded_params, distance_function)
    elif method_name == 'brutemaxbasin' or method_name == 'superfit':
        best_params_encoded, distance = optimize_brute(encoded_params, distance_function)
        logger.debug("Best grid parameters distance is (%f)." % distance)
        best_params_encoded, distance = optimize_basinhopping(best_params_encoded, distance_function)
    else:
        raise Exception("No such optimization method.")

    if initial_distance <= distance:
        logger.debug("Initial parameters (%f) are not worse than the best found (%f)." % (initial_distance, distance))
        return encoded_params, initial_distance
    else:
        return best_params_encoded, distance


def optimize_brute(params_to_optimize, distance_function):
    lower_bound = np.zeros(len(params_to_optimize), dtype=float)
    upper_bound = np.ones(len(params_to_optimize), dtype=float)

    # introduce random shift (0,grid step) # max 10%
    number_of_steps = 6
    step = (upper_bound - lower_bound) / float(number_of_steps)
    random_shift = np.array([random.random() * 1 / 10 for _ in range(len(lower_bound))], dtype=float)
    lower_bound += random_shift * step
    upper_bound += random_shift * step

    start = time.clock()
    result = opt.brute(distance_function, zip(lower_bound, upper_bound), finish=None, Ns=number_of_steps, disp=True,
                       full_output=True)
    elapsed = time.clock() - start

    logger.debug("Opt finished: " + str(result[:2]) + " Elapsed[s]: " + str(elapsed))

    return result[0], result[1]


def optimize_basinhopping(params_to_optimize, distance_function):
    bounds = RankBounds
    # minimizer_kwargs = {"method": "COBYLA", bounds=bounds}
    minimizer_kwargs = {"method": "L-BFGS-B", "bounds": zip(bounds.xmin, bounds.xmax)}
    result = opt.basinhopping(distance_function, params_to_optimize, accept_test=bounds,
                              minimizer_kwargs=minimizer_kwargs, niter=170)
    logger.debug("Opt finished: " + str(result))
    return result.x, result.fun


#
#
#   MULTIPROCESSING METHODS
#
#

def run_wrapper(queue, update_queue, images, gt_snakes, method, params):
    global callback_progress
    random.seed()  # reseed with random
    callback_progress = lambda p: update_queue.put(p)
    result = run_singleprocess(images[0], gt_snakes, method=method, initial_params=params, background_image=images[1],
                               ignore_mask=images[2])
    queue.put(result)


def multiproc_optimize(images, gt_snakes, method='brute', initial_params=None):
    return general_multiproc_fitting(run_wrapper, images, gt_snakes, method, initial_params)
