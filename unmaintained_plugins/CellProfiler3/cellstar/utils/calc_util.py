# -*- coding: utf-8 -*-
"""
Calculation package contains a number of functions used in contour grow and evaluation.
Date: 2013-2016
Website: http://cellstar-algorithm.org/
"""

import math

import numpy as np
import scipy.ndimage as sp_image

from index import Index


def euclidean_norm((x1, y1), (x2, y2)):
    return math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)


def interpolate_radiuses(values_mask, length, values):
    """
    Fill values with linear interpolation using values_mask values.
    @type values_mask: np.ndarray
    @param values_mask: mask of existing values
    @type values: np.ndarray
    @type length: int
    """
    cumlengths = np.where(values_mask)[0]
    if len(cumlengths) > 0:
        cumlengths_loop = np.append(cumlengths, cumlengths[0] + int(length))
        for i in range(len(cumlengths)):
            # Find left and right boundary in existing values.
            left_interval_boundary = cumlengths_loop[i]
            right_interval_boundary = cumlengths_loop[i + 1] % length

            # Length of the interpolated interval.
            interval_length = cumlengths_loop[i + 1] - left_interval_boundary - 1

            # Interpolate for every point in the interval.
            for k in range(1, interval_length + 1):
                interpolated = (left_interval_boundary + k) % length

                new_val = round(values[left_interval_boundary] +
                                (values[right_interval_boundary] - values[left_interval_boundary]) *
                                k / (interval_length + 1.0))  # (interval_length + 1.0)

                values[interpolated] = new_val  # min(values[interpolated], new_val)


def loop_connected_components(mask):
    """
    @type mask: np.ndarray
    @rtype (np.ndarray, np.ndarray, np.ndarray)
    """

    c = np.array([])
    init = np.array([])
    fin = np.array([])

    if mask.sum() > 0:
        labeled = sp_image.label(mask)[0]
        components = sp_image.measurements.find_objects(labeled)
        c_fin = [(s[0].stop - s[0].start, s[0].stop - 1) for s in components]
        if len(c_fin) > 1 and mask[0] and mask[-1]:
            c_fin[0] = c_fin[0][0] + c_fin[-1][0], c_fin[0][1]
            c_fin = c_fin[0:-1]

        c, fin = zip(*c_fin)
        c = np.array(c, dtype=int)
        fin = np.array(fin, dtype=int)
        init = (fin - c + 1) % mask.shape[0]
    return c, init, fin


def unstick_contour(edgepoints, unstick_coeff):
    """
    Removes edgepoints near previously discarded points.
    @type edgepoints: list[bool]
    @param edgepoints: current edgepoint list
    @type unstick_coeff: float
    @param unstick_coeff
    @return: filtered edgepoints
    """
    (n, init, end) = loop_connected_components(np.logical_not(edgepoints))
    filtered = np.copy(edgepoints)
    n_edgepoint = len(edgepoints)
    for size, s, e in zip(n, init, end):
        for j in range(1, int(size * unstick_coeff + 0.5) + 1):
            filtered[(e + j) % n_edgepoint] = 0
            filtered[(s - j) % n_edgepoint] = 0
    return filtered


def sub2ind(dim, (x, y)):
    return x + y * dim


def get_gradient(im, index, border_thickness_steps):
    """
    Fun. calc. radial gradient including thickness of cell edges
    @param im: image (for which grad. will be calc.)
    @param index: indices of pixes sorted by polar coordinates (alpha, radius)
    @param border_thickness_steps: number of steps to cop. grad. - depends on cell border thickness
    @return: gradient matrix for cell
    """
    # index of axis used to find max grad.
    max_gradient_along_axis = 2

    # preparing the image limits (called subimage) for which grad. will be computed
    radius_lengths, angles = index.shape[:2]

    # matrix init
    # for each single step for each border thick. separated grad. is being computed
    # at the end the max. grad values are returned (for all steps of thickness)
    border_thickness_steps = int(border_thickness_steps)
    gradients_for_steps = np.zeros((radius_lengths, angles, border_thickness_steps), dtype=np.float64)

    # for every step of thickness:
    for border_thickness_step in range(1, int(border_thickness_steps) + 1):
        # find beg. and end indices of input matrix for which the gradient will be computed
        matrix_end = radius_lengths - border_thickness_step
        matrix_start = border_thickness_step

        # find beg. and end indices of pix. for which the gradient will be computed
        starting_index = index[:matrix_end, :]
        ending_index = index[matrix_start:, :]

        # find internal in matrix where computed gradient will go
        intersect_start = int(math.ceil(border_thickness_step / 2.0))
        intersect_end = int(intersect_start + matrix_end)

        # comp. current gradient for selected (sub)image
        current_step_gradient = im[Index.to_numpy(ending_index)] - im[Index.to_numpy(starting_index)]
        current_step_gradient /= np.sqrt(border_thickness_step)

        # save gradient to previously determined place in results matrix
        gradients_for_steps[intersect_start:intersect_end, :, border_thickness_step - 1] = current_step_gradient

    return gradients_for_steps.max(axis=max_gradient_along_axis)


def extend_slices(my_slices, extension):
    def extend_slice(my_slice, extend):
        max_len = 100000
        ind = (max(0, my_slice.indices(max_len)[0] - extend), my_slice.indices(max_len)[1] + extend)
        return slice(*ind)

    return extend_slice(my_slices[0], extension), extend_slice(my_slices[1], extension)


def inslice_point(point_yx_in_slice, slices):
    y = point_yx_in_slice[0]
    x = point_yx_in_slice[1]
    max_len = 1000000
    return y - slices[0].indices(max_len)[0], x - slices[1].indices(max_len)[0]


def unslice_point(point_yx_in_slice, slices):
    y = point_yx_in_slice[0]
    x = point_yx_in_slice[1]
    max_len = 1000000
    return y + slices[0].indices(max_len)[0], x + slices[1].indices(max_len)[0]


def get_cartesian_bounds(polar_coordinate_boundary, origin_x, origin_y, polar_transform):
    polygon_x, polygon_y = polar_to_cartesian(polar_coordinate_boundary, origin_x, origin_y, polar_transform)
    x1 = int(max(0, math.floor(min(polygon_x))))
    x2 = int(math.ceil(max(polygon_x)) + 1)
    y1 = int(max(0, math.floor(min(polygon_y))))
    y2 = int(math.ceil(max(polygon_y)) + 1)
    return slice(y1, y2), slice(x1, x2)


def polar_to_cartesian(polar_coordinate_boundary, origin_x, origin_y, polar_transform):
    t = polar_transform.t
    step = polar_transform.step
    px = origin_x + step * polar_coordinate_boundary * np.cos(t.T)
    py = origin_y + step * polar_coordinate_boundary * np.sin(t.T)

    return px, py


def mask_with_pil(ys, xs, yslice, xslice):
    from PIL import Image
    rxs = np.round(xs) - xslice[0]
    rys = np.round(ys) - yslice[0]

    lx = xslice[1] - xslice[0]
    ly = yslice[1] - yslice[0]
    rxys = zip(rxs, rys)

    img = Image.new('L', (lx, ly), 0)
    draw = Image.core.draw(img.im, 0)
    ink = draw.draw_ink(1, "white")
    draw.draw_polygon(rxys, ink, 1)
    draw.draw_polygon(rxys, ink, 0)
    return np.array(img) != 0


def star_in_polygon((max_y, max_x), polar_coordinate_boundary, seed_x, seed_y, polar_transform):
    polygon_x, polygon_y = polar_to_cartesian(polar_coordinate_boundary, seed_x, seed_y, polar_transform)

    polygon_x_bounded = np.maximum(0, np.minimum(max_x - 1, polygon_x))
    polygon_y_bounded = np.maximum(0, np.minimum(max_y - 1, polygon_y))

    x1 = int(math.floor(np.min(polygon_x_bounded)))
    x2 = int(math.ceil(np.max(polygon_x_bounded)) + 1)
    y1 = int(math.floor(np.min(polygon_y_bounded)))
    y2 = int(math.ceil(np.max(polygon_y_bounded)) + 1)

    small_boolean_mask = mask_with_pil(polygon_y_bounded, polygon_x_bounded, (y1, y2), (x1, x2))

    boolean_mask = np.zeros((max_y, max_x), dtype=bool)
    boolean_mask[y1:y2, x1:x2] = small_boolean_mask

    yx = [y1, x1]

    return boolean_mask, small_boolean_mask, yx


def multiply_list(ls, times):
    list_length = len(ls)
    integer_times = int(times)
    fraction_elements = int((times - int(times)) * list_length)
    res = ls * integer_times
    res += ls[:fraction_elements]
    return res


def to_int(num):
    return int(num)


def fast_power(a, n):
    mn = a
    res = 1
    n = int(n)
    while n > 0:
        if (n % 2 == 1):
            res *= mn
        mn = mn * mn
        n /= 2
    return res