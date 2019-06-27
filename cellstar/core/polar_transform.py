# -*- coding: utf-8 -*-
"""
Polar transform provides tools for fast and convenient operation in polar domain.
Date: 2013-2016
Website: http://cellstar-algorithm.org/
"""

import math
import threading

import numpy as np

from cellstar.utils.calc_util import to_int
from cellstar.utils.calc_util import sub2ind
from cellstar.utils.image_util import image_dilate_with_element, get_circle_kernel


class PolarTransform(object):
    """
    Object wrapping polar transform calculations and cached properties

    @type N: int
    @ivar N: number of points for polar transform calculation

    @type distance: float
    @ivar distance: maximal distance from cell center to cell border

    @type step: float
    @ivar step: length of step for active contour along its axis in pixels

    @type steps: int
    @ivar steps: number of steps considered for active contour along single axis

    @type max_r: int
    @ivar max_r: maximal radius of active contour

    @type R: numpy.array
    @ivar R: consecutive radii values for single axis of active contour

    @type center: int
    @ivar center: Polar transform center coordinate

    @type edge: int
    @ivar edge: dimension of polar transform

    @type halfedge: int
    @ivar halfedge: half of polar transform dimension

    @type t: numpy.array
    @ivar t: angles (in radians) of consecutive rays casted from 'center'

    @type x: numpy.array
    @ivar x: cartesian x-coordinates of points in polar coordinates system
    coordinates ordered by radius of polar points --> x[r,a] = P(r,a).x

    @type y: numpy.array
    @ivar y: cartesian y-coordinates of points in polar coordinates system
    coordinates ordered by radius of polar points --> y[r,a] = P(r,a).y

    @type dot_voronoi: numpy.array
    @ivar dot_voronoi - voronoi - "gravity field" of contour points
    dot_voronoi[x,y] = id(closest_contour_point(x,y))

    @type to_polar: dict
    @ivar to_polar - dictionary of lists
    for each point:
    to_polar[index(P(R,a)] - list of point id in voronoi of contour points {P(r,a)| 0 < r < R}
    to_polar[index(P(R,a)] = [gravity_field(dot_voronoi, p) for p in {P(r,a) | 0 < r < R}]
    to_polar[index(P(R,a)] =
        [index(x,y) for x,y in range((0,0),(edge,edge)) if dot_voronoi[x,y] == gravity_index(p) for p in {P(r,a) | 0 < r < R}]
    """

    __singleton_lock = threading.Lock()
    __singleton_instances = {}

    @classmethod
    def instance(cls, avg_cell_diameter, points, step, max_size):
        init_params = avg_cell_diameter, points, step, max_size
        if not cls.__singleton_instances.get(init_params, False):
            with cls.__singleton_lock:
                if not cls.__singleton_instances.get(init_params, False):
                    cls.__singleton_instances[init_params] = cls(avg_cell_diameter, points, step, max_size)
        return cls.__singleton_instances.get(init_params, None)

    def __init__(self, avg_cell_diameter, points_number, step, max_size):
        self.N = points_number
        self.distance = max_size * avg_cell_diameter
        self.step = max(step * avg_cell_diameter, 0.2)
        self.steps = 1 + int(round((self.distance + 2) / self.step))
        self.max_r = min(1 + int(round(self.distance / self.step)), self.steps - 1)

        self.R = None
        self.center = None
        self.edge = None
        self.half_edge = None
        self.x = None
        self.y = None

        self.dot_voronoi = None
        self.to_polar = {}

        self._calculate_polar_transform()

    def _calculate_polar_transform(self):
        self.R = np.arange(1, self.steps + 1).reshape((1, self.steps)).transpose() * self.step

        # rays angle from cell center
        self.t = np.linspace(0, 2 * math.pi, self.N + 1)
        self.t = self.t[:-1]

        # sinus and cosinus of rays angle repeated steps-times
        # function value for angles and every radius (for a given angle same for every radius)
        sin_t = np.kron(np.ones((len(self.R), 1)), np.sin(self.t))
        cos_t = np.kron(np.ones((len(self.R), 1)), np.cos(self.t))

        # N-times repeated vector of subsequent radiuses
        RR = np.kron(np.ones((1, len(self.t))), self.R)

        # From polar definition:
        # x - matrix of xs for angle alpha and radius R
        # y - matrix of ys for angle alpha and radius R
        self.x = RR * cos_t
        self.y = RR * sin_t

        self.half_edge = math.ceil(self.R[-1] + 2)
        self.center = to_int(self.half_edge + 1)
        self.edge = to_int(self.center + self.half_edge)

        # clear black image [edge x edge]
        self.dot_voronoi = np.zeros((self.edge, self.edge), dtype=int)
        px = self.center + self.x
        py = self.center + self.y

        # create list of coordinates (x,y) on the checked contour
        index = np.column_stack(((py - .5).astype(int).T.flat, (px - .5).astype(int).T.flat))

        # create list of subsequent id for above points
        cont = np.arange(1, px.size + 1)

        # mark on 'dot_voronoi' every point using unique id
        self.dot_voronoi[tuple(index.T)] = cont

        # in every iteration smooth 'dot_voronoi' marking gravity field of given points
        for i in range(0, int(self.center)):
            ndv = image_dilate_with_element(self.dot_voronoi, 3)
            mask = np.logical_and((self.dot_voronoi == 0), (ndv != 0))
            mask = mask.nonzero()
            self.dot_voronoi[mask] = ndv[mask]

        # apply circle mask on 'dot_voronoi'
        circ_mask = get_circle_kernel(self.half_edge)
        self.dot_voronoi[np.logical_not(circ_mask)] = 0
        self.dot_voronoi[self.center - 1, self.center - 1] = 0

        # for every angle
        for a in range(self.t.size):
            # create new clear mask
            mask = np.zeros((self.edge, self.edge), dtype=bool)
            # for point
            for r in range(self.R.size):
                # find index of point P(r,a)
                idx = sub2ind(px.shape[0], (r, a))
                val = idx + 1
                # find places which belong to that index in 'dot_voronoi'
                indices = np.array(zip(*np.nonzero(self.dot_voronoi == val)))
                # set mask to 1 in above places
                if len(indices) > 0:
                    mask[tuple(indices.T)] = 1

                # to_polar[idx] is a list of coordinates (x,y) from points on the mask
                self.to_polar[idx] = map(lambda pair: pair, zip(*np.nonzero(mask)))
