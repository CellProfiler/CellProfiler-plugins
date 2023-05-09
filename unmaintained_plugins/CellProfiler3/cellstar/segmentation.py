# -*- coding: utf-8 -*-
"""
Segmentation is a main entry point for CellStar segmentation.
Date: 2013-2016
Website: http://cellstar-algorithm.org/
"""

import ast
import logging

logger = logging.getLogger(__name__)
from copy import copy

from cellstar.utils.params_util import *
from cellstar.core.image_repo import ImageRepo
from cellstar.utils.params_util import default_parameters
from cellstar.utils import image_util, debug_util
from cellstar.core.seeder import Seeder
from cellstar.core.snake import Snake
from cellstar.core.snake_filter import SnakeFilter
from cellstar.core.polar_transform import PolarTransform
from cellstar.parameter_fitting.pf_auto_params import rank_parameters_range as rank_auto_params
from cellstar.parameter_fitting.pf_auto_params import parameters_range as snake_auto_params


class Segmentation(object):
    def __init__(self, segmentation_precision=9, avg_cell_diameter=35):
        self.parameters = default_parameters(segmentation_precision, avg_cell_diameter)
        self.images = None
        self.all_seeds = []
        self.seeds = []
        self.grown_seeds = set()  # seeds from which we already have snakes
        self.snakes = []
        self.new_snakes = []
        self._seeder = None
        self._filter = None
        self.polar_transform = PolarTransform.instance(self.parameters["segmentation"]["avgCellDiameter"],
                                                       self.parameters["segmentation"]["stars"]["points"],
                                                       self.parameters["segmentation"]["stars"]["step"],
                                                       self.parameters["segmentation"]["stars"]["maxSize"])
        self.debug_output_image_path = None

    @property
    def seeder(self):
        if self._seeder is None:
            self.init_seeder()

        return self._seeder

    @property
    def filter(self):
        if self._filter is None:
            self.init_filter()

        return self._filter

    def clear_lists(self):
        self.all_seeds = []
        self.seeds = []
        self.grown_seeds = set()
        self.snakes = []
        self.new_snakes = []

    def set_frame(self, frame):
        # Extract previous background
        prev_background = None
        if self.images is not None:
            prev_background = self.images.background
        # Initialize new image repository for new frame
        self.images = ImageRepo(frame, self.parameters)
        # One background per whole segmentation
        if prev_background is not None:
            self.images.background = prev_background

        # Clear all temporary results
        self.clear_lists()

    def set_background(self, background):
        self.images._background = background

    def set_mask(self, ignore_mask):
        if ignore_mask is not None:
            self.images.apply_mask(ignore_mask)

    def init_seeder(self):
        self._seeder = Seeder(self.images, self.parameters)

    def init_filter(self):
        self._filter = SnakeFilter(self.images, self.parameters)

    def decode_auto_params(self, text):
        """
        Decode automatic parameters from text and apply to self.

        @param text: parameters denoted as python list
        @return true if parsing was successful
        """
        return Segmentation.decode_auto_params_into(self.parameters, text)

    @staticmethod
    def decode_auto_params_into(complete_params, text):
        """
        Decode automatic parameters from text and apply to self.

        @param text: parameters denoted as python list
        @return true if parsing was successful
        """
        new_stars = copy(complete_params["segmentation"]["stars"])
        new_ranking = copy(complete_params["segmentation"]["ranking"])
        try:
            all_params = ast.literal_eval(text)
            snake_params = all_params[0]
            rank_params = all_params[1]
            if len(snake_params) != len(snake_auto_params) or len(rank_params) != len(rank_auto_params):
                raise Exception("text invalid: list size not compatible")

            for name in sorted(snake_auto_params.keys()):
                val = snake_params[0]
                if name == "sizeWeight":  # value to list
                    original = complete_params["segmentation"]["stars"]["sizeWeight"]
                    val = list(np.array(original) * (val/np.mean(original)))

                new_stars[name] = val
                snake_params = snake_params[1:]

            for name in sorted(rank_auto_params.keys()):
                new_ranking[name] = rank_params[0]
                rank_params = rank_params[1:]
        except:
            return False

        complete_params["segmentation"]["stars"] = new_stars
        complete_params["segmentation"]["ranking"] = new_ranking
        return True

    @staticmethod
    def encode_auto_params_from_all_params(parameters):
        snake_auto_params_values = []
        for name in sorted(snake_auto_params.keys()):
            val = parameters["segmentation"]["stars"][name]
            if name == "sizeWeight":  # list to mean value
                original = parameters["segmentation"]["stars"]["sizeWeight"]
                val = np.mean(original)
            snake_auto_params_values.append(val)

        rank_auto_params_values = [parameters["segmentation"]["ranking"][name]
                                   for name in sorted(rank_auto_params.keys())]
        auto_values_list = [snake_auto_params_values, rank_auto_params_values]

        return str(auto_values_list)

    def encode_auto_params(self):
        return Segmentation.encode_auto_params_from_all_params(self.parameters)

    def pre_process(self):
        # background getter is never None but it creation background only if not existant
        if self.images.background is None:
            self.images.calculate_background()

        self.images.calculate_brighter_original()
        self.images.calculate_darker_original()
        self.images.calculate_clean_original()
        self.images.calculate_forebackground_masks()

        self.images.calculate_clean()
        self.images.calculate_brighter()
        self.images.calculate_darker()

        self.images.calculate_cell_border_content_mask()

    def find_seeds(self, exclude):
        self.seeds = self.seeder.find_seeds(self.snakes, self.all_seeds, exclude_current_segments=exclude)
        self.all_seeds += self.seeds

    def snakes_from_seeds(self):
        self.new_snakes = [
            Snake.create_from_seed(
                self.parameters, seed, self.parameters["segmentation"]["stars"]["points"], self.images
            )
            for seed in self.seeds if seed not in self.grown_seeds
        ]
        for seed in self.seeds:
            if seed not in self.grown_seeds:
                self.grown_seeds.add(seed)

    def grow_snakes(self):
        grown_snakes = []
        size_weights = self.parameters["segmentation"]["stars"]["sizeWeight"]
        logger.debug("%d snakes seeds to grow with %d weights options -> %d snakes to calculate"%(len(self.new_snakes), len(size_weights), len(self.new_snakes) * len(size_weights)))
        for snake in self.new_snakes:
            best_snake = None
            for weight in size_weights:
                curr_snake = copy(snake)

                curr_snake.grow(weight, self.polar_transform)
                curr_snake.evaluate(self.polar_transform)

                if best_snake is None:
                    best_snake = curr_snake
                else:
                    if curr_snake.rank < best_snake.rank:
                        best_snake = curr_snake

            grown_snakes.append(best_snake)

        self.new_snakes = grown_snakes

    def evaluate_snakes(self):
        for snake in self.new_snakes:
            snake.evaluate(self.polar_transform)

    def filter_snakes(self):
        self.snakes = self.filter.filter(self.snakes + self.new_snakes)
        self.new_snakes = []

    def debug_images(self):
        if self.debug_output_image_path is not None:
            debug_util.debug_image_path = self.debug_output_image_path
        debug_util.images_repo_save(self.images)

    def debug_seeds(self, step):
        if self.debug_output_image_path is not None:
            image_util.debug_image_path = self.debug_output_image_path
        debug_util.draw_seeds(self.all_seeds, self.images.image, title=str(step))

    def run_one_step(self, step):
        logger.debug("find_seeds")
        self.find_seeds(step > 0)
        self.debug_seeds(step)
        logger.debug("snake_from_seeds")
        self.snakes_from_seeds()
        logger.debug("grow_snakes")
        self.grow_snakes()
        logger.debug("filter_snakes")
        debug_util.draw_snakes(self.images.image, self.snakes + self.new_snakes, it=step)
        self.filter_snakes()
        logger.debug("done")

    def run_segmentation(self):
        logger.debug("preproces...")
        self.pre_process()
        self.debug_images()
        debug_util.explore_cellstar(self)
        for step in range(self.parameters["segmentation"]["steps"]):
            self.run_one_step(step)
        return self.images.segmentation, self.snakes