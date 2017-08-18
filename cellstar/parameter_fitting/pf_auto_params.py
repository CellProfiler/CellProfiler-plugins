# -*- coding: utf-8 -*-
"""
Pf auto params contains parameters that are optimised as well as encode / decode functions.
Date: 2013-2016
Website: http://cellstar-algorithm.org/
"""

import numpy as np

parameters_range = {#"borderThickness": (0.001, 1.0),
                    "brightnessWeight": (-0.4, 0.4),
                    "cumBrightnessWeight": (0, 500),
                    "gradientWeight": (-30, 30),
                    "sizeWeight": (10, 300),
                    #"smoothness": (3, 8)
}

rank_parameters_range = {"avgBorderBrightnessWeight": (0, 600),
                         "avgInnerBrightnessWeight": (-100, 100),
                         "avgInnerDarknessWeight": (-100, 100),
                         "logAreaBonus": (5, 50),
                         "maxInnerBrightnessWeight": (-10, 50),
                         # "maxRank": (5, 300),
                         # "stickingWeight": (0, 120)  # this is set to 60 rest of parameters should adapt to it
}


class OptimisationBounds(object):
    def __init__(self, size=None, xmax=1, xmin=0):
        self.xmax = xmax
        self.xmin = xmin
        if size is not None:
            self.xmax = [xmax] * size
            self.xmin = [xmin] * size

    @staticmethod
    def from_ranges(ranges_dict):
        bounds = OptimisationBounds()
        bounds.xmin = []
        bounds.xmax = []
        # bound only two parameters
        for k, v in list(sorted(ranges_dict.iteritems())):
            if k == "borderThickness":
                bounds.xmin.append(0.001)
                bounds.xmax.append(2)
            elif k == "smoothness":
                bounds.xmin.append(4.0)
                bounds.xmax.append(10.0)
            else:
                bounds.xmin.append(-1000000)
                bounds.xmax.append(1000000)

        # bounds.xmin, bounds.xmax = zip(*zip(*list(sorted(ranges_dict.iteritems())))[1])
        return bounds

    def __call__(self, **kwargs):
        x = kwargs["x_new"]
        tmax = bool(np.all(x <= self.xmax))
        tmin = bool(np.all(x >= self.xmin))
        return tmax and tmin


ContourBounds = OptimisationBounds.from_ranges(parameters_range)
RankBounds = OptimisationBounds(size=len(rank_parameters_range))


#
#
# PARAMETERS ENCODE DECODE
#
#

def pf_parameters_encode(parameters):
    """
    brightnessWeight: 0.0442 +brightness on cell edges
    cumBrightnessWeight: 304.45 -brightness in the cell center
    gradientWeight: 15.482 +gradent on the cell edges
    sizeWeight: 189.4082 (if list -> avg. will be comp.) +big cells
    @param parameters: dictionary segmentation.stars
    """
    parameters = parameters["segmentation"]["stars"]
    point = []
    for name, (_, _) in sorted(parameters_range.iteritems()):
        val = parameters[name]
        if name == "sizeWeight":
            if not isinstance(val, float):
                val = np.mean(val)
        point.append(val)  # no scaling
    return point


def pf_parameters_decode(param_vector, org_size_weights_list):
    """
    sizeWeight is one number (mean of the future list)
    @type param_vector: numpy.ndarray
    @return:
    """
    parameters = {}
    for (name, (_, _)), val in zip(sorted(parameters_range.iteritems()), param_vector):
        if name == "sizeWeight":
            val = list(np.array(org_size_weights_list) * (val / np.mean(org_size_weights_list)))
        elif name == "borderThickness":
            val = min(max(0.001, val), 3)
        parameters[name] = val

    # set from default
    parameters["borderThickness"] = 0.1
    parameters["smoothness"] = 6
    return parameters


def pf_rank_parameters_encode(parameters, complete_params_given=True):
    """
    avgBorderBrightnessWeight: 300
    avgInnerBrightnessWeight: 10
    avgInnerDarknessWeight: 0
    logAreaBonus: 18
    maxInnerBrightnessWeight: 10
    @param parameters: dictionary all ranking params or a complete
    @param complete_params_given: is parameters a complete dictionary
    """
    if complete_params_given:
        parameters = parameters["segmentation"]["ranking"]

    point = []
    for name, (vmin, vmax) in sorted(rank_parameters_range.iteritems()):
        val = parameters[name]
        if vmax - vmin == 0:
            point.append(0)
        else:
            point.append((val - vmin) / float(vmax - vmin))  # scaling to [0,1]
    return point


def pf_rank_parameters_decode(param_vector):
    """
    @type param_vector: numpy.ndarray
    @return: only ranking parameters as a dict
    """
    parameters = {}
    for (name, (vmin, vmax)), val in zip(sorted(rank_parameters_range.iteritems()), param_vector):
        rescaled = vmin + val * (vmax - vmin)
        parameters[name] = rescaled

    # set from default
    parameters["stickingWeight"] = 60

    return parameters
