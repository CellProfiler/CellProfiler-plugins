# -*- coding: utf-8 -*-
"""
Mutator can be used to change (ie mutate) existing snakes to provide higher variability in ground_truth pool.
Date: 2013-2016
Website: http://cellstar-algorithm.org/
"""

import copy
import random

import numpy as np

from cellstar.core.point import *
from cellstar.utils.calc_util import polar_to_cartesian


def add_mutations(gt_and_grown, avg_cell_diameter):
    mutants = []
    mutation_radiuses = 0.2 * avg_cell_diameter
    for (gt, grown) in gt_and_grown:
        mutants += [
            (gt, grown.create_mutation(mutation_radiuses * 2, random_poly=True)),
            (gt, grown.create_mutation(-mutation_radiuses * 2, random_poly=True)),
            (gt, grown.create_mutation(mutation_radiuses)), (gt, grown.create_mutation(-mutation_radiuses)),
        ]
    return gt_and_grown + mutants


def create_mutant_from_change(org_snake, polar_transform, boundary_change):
    mutant_snake = copy.copy(org_snake)
    # zero rank so it recalculates
    mutant_snake.rank = None

    # constrain change
    new_boundary = mutant_snake.polar_coordinate_boundary + boundary_change
    while (new_boundary <= 3).all() and abs(boundary_change).max() > 3:
        new_boundary = np.maximum(np.minimum(
            mutant_snake.polar_coordinate_boundary + boundary_change,
            len(polar_transform.R) - 1), 3)
        boundary_change /= 1.3

    px, py = polar_to_cartesian(new_boundary, mutant_snake.seed.x, mutant_snake.seed.y, polar_transform)

    mutant_snake.polar_coordinate_boundary = new_boundary
    mutant_snake.points = [Point(x, y) for x, y in zip(px, py)]

    # need to update self.final_edgepoints to calculate properties (for now we ignore this property)
    mutant_snake.evaluate(polar_transform)

    return mutant_snake


def create_poly_mutation(org_snake, polar_transform, max_diff):
    # change to pixels
    length = org_snake.polar_coordinate_boundary.size
    max_diff /= polar_transform.step

    def polynomial(x1, x2):
        def eval(x):
            return x * (x - length) * (x - x1) * (x * 0.4 - x2)

        return eval

    poly = polynomial(random.uniform(0.001, length), random.uniform(0.001, length))
    boundary_change = np.array([poly(x) for x in range(length)])

    M = abs(boundary_change).max()
    boundary_change = boundary_change / M * max_diff

    mutant_snake = create_mutant_from_change(org_snake, polar_transform, boundary_change)
    return mutant_snake


def create_mutation(org_snake, polar_transform, dilation):
    # change to pixels
    dilation /= polar_transform.step
    boundary_change = np.array([dilation for _ in range(org_snake.polar_coordinate_boundary.size)])

    mutant_snake = create_mutant_from_change(org_snake, polar_transform, boundary_change)
    return mutant_snake
