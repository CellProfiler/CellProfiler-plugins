# -*- coding: utf-8 -*-
"""
PFRankSnake represents one ground_truth contour for ranking parameters fitting.
Date: 2013-2016
Website: http://cellstar-algorithm.org/
"""

import copy
import random

random.seed(1)  # make it deterministic

from cellstar.core.polar_transform import PolarTransform
from cellstar.parameter_fitting.pf_snake import PFSnake
import pf_mutator


class PFRankSnake(object):
    def __init__(self, gt_snake, grown_snake, avg_cell_diameter, params):
        self.gt_snake = gt_snake
        self.grown_snake = grown_snake
        self.avg_cell_diameter = avg_cell_diameter
        self.initial_parameters = params
        self.fitness = PFSnake.fitness_with_gt(grown_snake, gt_snake)
        self.rank_vector = grown_snake.properties_vector(avg_cell_diameter)
        self.polar_transform = PolarTransform.instance(params["segmentation"]["avgCellDiameter"],
                                                       params["segmentation"]["stars"]["points"],
                                                       params["segmentation"]["stars"]["step"],
                                                       params["segmentation"]["stars"]["maxSize"])

    @staticmethod
    def create_all(gt_snake, grown_pf_snake, params):
        return [(gt_snake, PFRankSnake(gt_snake, snake, grown_pf_snake.avg_cell_diameter, params)) for snake in
                grown_pf_snake.snakes]

    def create_mutation(self, dilation, random_poly=False):
        if random_poly:
            mutant = pf_mutator.create_poly_mutation(self.grown_snake, self.polar_transform, dilation)
        else:
            mutant = pf_mutator.create_mutation(self.grown_snake, self.polar_transform, dilation)
        return PFRankSnake(self.gt_snake, mutant, self.avg_cell_diameter, self.initial_parameters)

    @staticmethod
    def merge_rank_parameters(initial_parameters, new_params):
        params = copy.deepcopy(initial_parameters)
        for k, v in new_params.iteritems():
            params["segmentation"]["ranking"][k] = v

        return params

    def merge_parameters_with_me(self, new_params):
        return PFRankSnake.merge_rank_parameters(self.initial_parameters, new_params)

    def calculate_ranking(self, ranking_params):
        return self.grown_snake.star_rank(ranking_params, self.avg_cell_diameter)
