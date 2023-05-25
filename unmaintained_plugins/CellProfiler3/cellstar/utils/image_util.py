# -*- coding: utf-8 -*-
"""
Image util module contains additional methods for easy image manipulations.
Date: 2013-2016
Website: http://cellstar-algorithm.org/
"""

import numpy as np
import scipy as sp
import scipy.misc
import scipy.ndimage
from numpy import argwhere
from numpy.fft import rfft2, irfft2
from scipy.ndimage.filters import *

try:
    #  for older version of scipy
    from scipy.signal.signaltools import _next_regular as next_fast_len
except:
    #  for 0.19 version of scipy
    from scipy.fftpack.helper import next_fast_len


from calc_util import extend_slices, fast_power, to_int


def fft_convolve(in1, in2, times):
    def _centered(arr, newsize):
        # Return the center newsize portion of the array.
        currsize = np.array(arr.shape)
        startind = (currsize - newsize) // 2
        endind = startind + newsize
        myslice = [slice(startind[k], endind[k]) for k in range(len(endind))]
        return arr[tuple(myslice)]

    if times == 0:
        return in1.copy()


    s1 = np.array(in1.shape)
    s2 = np.array(in2.shape)
    shape = s1 + (s2 - 1) * times

    # Speed up FFT by padding to optimal size for FFTPACK
    fshape = [next_fast_len(int(d)) for d in shape]
    fslice = tuple([slice(0, int(sz)) for sz in shape])

    resfft = fast_power(rfft2(in2, fshape), times)
    resfft = resfft * rfft2(in1, fshape)
    ret = irfft2(resfft, fshape)[fslice].copy()
    ret = ret.real

    return _centered(ret, s1)


def get_bounding_box(image_mask):
    """
    Calculates the minimal bounding box for non zero elements.
    @returns [ystart,ystop), [xstart,xstop) or None, None
    """
    non_zero_points = argwhere(image_mask)
    if len(non_zero_points) == 0:
        return None
    (ystart, xstart), (ystop, xstop) = non_zero_points.min(0), non_zero_points.max(0) + 1
    return (ystart, ystop), (xstart, xstop)


def get_circle_kernel(radius):
    """
    Creates radius x radius bool image of the circle.
    @param radius: radius of the circle
    """
    y, x = np.ogrid[np.floor(-radius):np.ceil(radius) + 1, np.floor(-radius):np.ceil(radius) + 1]
    return x ** 2 + y ** 2 <= radius ** 2


def image_dilate(image, radius):
    image = np.copy(image)
    if radius <= 1:
        return image

    box = get_bounding_box(image)
    if box is None:
        return image
    ys, xs = box
    lp, hp = contain_pixel(image.shape, (ys[0] - radius, xs[0] - radius)), \
             contain_pixel(image.shape, (ys[1] + radius, xs[1] + radius))
    ys, xs = (lp[0], hp[0]), (lp[1], hp[1])
    morphology_element = get_circle_kernel(radius)
    dilated_part = sp.ndimage.morphology.binary_dilation(image[ys[0]:ys[1], xs[0]:xs[1]], morphology_element)
    image[ys[0]:ys[1], xs[0]:xs[1]] = dilated_part
    return image


def image_dilate_with_element(image, n):
    return sp.ndimage.morphology.grey_dilation(image, size=(n, n))


def image_erode(image, radius):
    morphology_element = get_circle_kernel(radius)
    return sp.ndimage.morphology.binary_erosion(image, morphology_element)


def fill_foreground_holes(mask, kernel_size, minimal_hole_size, min_cluster_area_scaled, mask_min_radius_scaled):
    filled_black_holes = fill_holes(mask, kernel_size, minimal_hole_size)

    holes_remaining = np.logical_not(filled_black_holes)
    filled_small_holes = mark_small_areas(holes_remaining, min_cluster_area_scaled, filled_black_holes)

    morphology_enhanced = image_erode(filled_small_holes, mask_min_radius_scaled)
    morphology_enhanced = image_dilate(morphology_enhanced, mask_min_radius_scaled)

    dilated_mask = dilate_big_areas(morphology_enhanced, min_cluster_area_scaled, kernel_size)

    return dilated_mask


def mark_small_areas(mask, max_hole_size, result_mask):
    components, num_components = sp.ndimage.label(mask, np.ones((3, 3)))
    slices = sp.ndimage.find_objects(components)
    for label, slice in zip(range(1, num_components + 1), slices):
        components_slice = components[slice] == label
        if np.count_nonzero(components_slice) < max_hole_size:
            result_mask[slice][components_slice] = True
    return result_mask


def dilate_big_areas(mask, min_area_size, dilate_radius):
    components, num_components = sp.ndimage.label(mask, np.ones((3, 3)))
    component = np.zeros(mask.shape, dtype=bool)
    for label in range(1, num_components + 1):
        np.equal(components, label, component)
        if np.count_nonzero(component) > min_area_size:
            tmp_mask = image_dilate(component, dilate_radius)
            mask = mask | tmp_mask

    return mask


def fill_holes(mask, kernel_size, minimal_hole_size):
    """
    Fills holes in a given mask using iterative close + dilate morphological operations and filtering small patches.
    @param mask: mask which holes are to be filled
    @param kernel_size: size of the morphological element used to dilate/erode mask
    @param minimal_hole_size: holes with area smaller than param are to be removed
    """
    nr = 1
    morphology_element = get_circle_kernel(kernel_size)
    while True:
        new_mask = mask.copy()
        # find connected components
        components, num_components = sp.ndimage.label(np.logical_not(new_mask), np.ones((3, 3)))
        slices = sp.ndimage.find_objects(components)
        for label, slice in zip(range(1, num_components + 1), slices):
            slice = extend_slices(slice, to_int(kernel_size * 2))
            components_slice = components[slice] == label
            # filter small components
            if np.count_nonzero(components_slice) < minimal_hole_size:
                new_mask[slice] |= components_slice
            else:
                # shrink components and check if they fell apart
                # close holes
                components_slice = sp.ndimage.morphology.binary_closing(components_slice, morphology_element)

                # erode holes
                components_slice = sp.ndimage.morphology.binary_erosion(components_slice, morphology_element)

                # don't invade masked pixels
                components_slice &= np.logical_not(new_mask[slice])

                # recount connected components and check sizes
                mark_small_areas(components_slice, minimal_hole_size, new_mask[slice])

        # check if it is the fix point
        if (mask == new_mask).all():
            break
        else:
            mask = new_mask

        nr += 1

    return mask


def contain_pixel(shape, pixelYX):
    """
    Trims pixel to given dimentions, converts pixel position to int
    @param shape: size (height, width) exclusive
    @param pixel: pixel to push inside shape
    """
    (py, px) = pixelYX
    (py, px) = ((np.minimum(np.maximum(py + 0.5, 0), shape[0] - 1)).astype(int),
                (np.minimum(np.maximum(px + 0.5, 0), shape[1] - 1)).astype(int))
    return py, px


def find_maxima(image):
    """
    Finds local maxima in given image
    @param image: image for which maxima will be found
    """
    height = image.shape[0]
    width = image.shape[1]

    right = np.zeros(image.shape, dtype=bool)
    left = np.zeros(image.shape, dtype=bool)
    up = np.zeros(image.shape, dtype=bool)
    down = np.zeros(image.shape, dtype=bool)

    right[:, 0:width - 1] = image[:, 0:width - 1] > image[:, 1:width]
    left[:, 1:width] = image[:, 1:width] > image[:, 0:width - 1]
    up[0:height - 1, :] = image[0:height - 1, :] > image[1:height, :]
    down[1:height, :] = image[1:height, :] > image[0:height - 1, :]

    return right & left & up & down


def exclude_segments(image, segments, val):
    """
    Sets exclusion value for given segments in given image
    @param image: image from which segments will be excluded
    @param segments: segments to be excluded from image
    @param val: value to be set in segments as exclusion value
    """
    segment_mask = segments > 0
    inverted_segment_mask = np.logical_not(segment_mask)
    image_segments_zeroed = image * inverted_segment_mask
    image_segments_valued = image_segments_zeroed + (segment_mask * val)

    return image_segments_valued


def image_median_filter(image, size):
    if size < 1:
        return image
    
    size = to_int(size)
    return median_filter(image, (size, size))


def image_blur(image, times):
    """
    Performs image blur with kernel: [[2, 3, 2], [3, 12, 3], [2, 3, 2]] / 32
    @param image: image to be blurred (assumed as numpy.array of values from 0 to 1)
    @param times: specifies how many times blurring will be performed
    """
    kernel = np.array([[2, 3, 2], [3, 12, 3], [2, 3, 2]]) / 32.0

    if times >= 8:
        return fft_convolve(image, kernel, times)
    else:
        blurred = convolve(image, kernel)
        for _ in xrange(int(times) - 1):
            blurred = convolve(blurred, kernel)
        return blurred


def image_smooth(image, radius, fft_use=True):
    """
    Performs image blur with circular kernel.
    @param image: image to be blurred (assumed as numpy.array of values from 0 to 1)
    @param radius: radius of the kernel
    """
    if radius < 1:
        return image

    kernel = get_circle_kernel(radius).astype(float)
    kernel /= np.sum(kernel)
    image = np.array(image, dtype=float)

    if radius >= 8 and fft_use:
        image_2 = np.pad(image, int(radius), mode='reflect')
        res = fft_convolve(image_2, kernel, 1)
        radius_round = to_int(radius)
        return res[radius_round:-radius_round, radius_round:-radius_round]
    else:
        return convolve(image, kernel, mode='reflect', cval=0.0)


def image_normalize(image):
    """
    Performs image normalization (vide: matlab mat2gray)
    @param image: image to be normalized (assumed as numpy.array of values from 0 to 1)
    """
    minimum = np.amin(image)
    maximum = np.amax(image)

    delta = 1
    if maximum != minimum:
        delta = 1 / (maximum - minimum)
    shift = - minimum * delta

    image_normalized = delta * image + shift

    return np.minimum(np.maximum(image_normalized, 0), 1)


def set_image_border(image, val):
    """
    Sets pixel values at image borders to given value
    @param image: image that borders will be set to given value
    @param val: value to be s et
    """
    image[0, :] = val
    image[:, 0] = val
    image[image.shape[0] - 1, :] = val
    image[:, image.shape[1] - 1] = val

    return image


def load_image(filename, scaling=True):
    if filename == '':
        return None
    image = scipy.misc.imread(filename)
    if image.max() > 1 and scaling:
        image2d = np.array(image, dtype=float) / np.iinfo(image.dtype).max
    else:
        image2d = image.astype(float)

    if image2d.ndim == 3:
        image2d = np.sum(image, 2) / image.shape[2]
    return image2d
