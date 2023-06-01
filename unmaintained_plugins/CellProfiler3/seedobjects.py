# coding=utf-8

"""
SeedObjects
===========

**SeedObjects** generates *seeds* or *markers* based on an input set of objects.

**SeedObjects** can be run *before* any module that uses seeds (e.g., **Watershed**).
Seeds are generated from the objects in a four step process:

#. Compute the `Euclidean distance transformation`_ of the segmented objects

#. Smooth the transformed image with a Gaussian filter

#. Compute the `local maxima`_

#. Dilate the seeds as specified

This algorithm attempts to locate the centers of objects even if they are under-segmented.

.. Euclidean distance transformation: https://docs.scipy.org/doc/scipy-0.14.0/reference/generated/scipy.ndimage.morphology.distance_transform_edt.html
.. local maxima: http://scikit-image.org/docs/dev/api/skimage.feature.html#peak-local-max

|

============ ============ ===============
Supports 2D? Supports 3D? Respects masks?
============ ============ ===============
YES          YES          NO
============ ============ ===============

"""

import numpy
import numpy.random
import skimage.morphology
import skimage.segmentation
import scipy.ndimage
import skimage.filters
import skimage.feature
import skimage.util

import cellprofiler.image
import cellprofiler.module
import cellprofiler.setting


class SeedObjects(cellprofiler.module.ObjectProcessing):
    category = "Advanced"

    module_name = "SeedObjects"

    variable_revision_number = 1

    def create_settings(self):
        super(SeedObjects, self).create_settings()

        self.gaussian_sigma = cellprofiler.setting.Float(
            text="Standard deviation for Gaussian kernel",
            value=1.,
            doc="Sigma defines how 'smooth' the Gaussian kernal makes the image. Higher sigma means a smoother image."
        )

        self.min_dist = cellprofiler.setting.Integer(
            text="Minimum distance between seeds",
            value=1,
            minval=0,
            doc="""\
Minimum number of pixels separating peaks in a region of `2 * min_distance + 1 `
(i.e. peaks are separated by at least min_distance). 
To find the maximum number of peaks, set this value to `1`. 
"""
        )

        self.min_intensity = cellprofiler.setting.Float(
            text="Minimum absolute internal distance",
            value=0.,
            minval=0.,
            maxval=1.,
            doc="""\
Minimum absolute intensity threshold for seed generation. Since this threshold is
applied to the distance transformed image, this defines a minimum object
"size". Objects smaller than this size will not contain seeds. 

This value is expressed as a percentage value (as if the image were rescaled
between 0 and 1). 

By default, the absolute threshold is the minimum value of the image.
For distance transformed images, this value is `0` (or the background).
"""
        )

        self.exclude_border = cellprofiler.setting.Integer(
            text="Pixels from border to exclude",
            value=0,
            minval=0,
            doc="Exclude seed generation from within `n` pixels of the image border."
        )

        self.max_seeds = cellprofiler.setting.Integer(
            text="Maximum number of seeds",
            value=-1,
            doc="""\
Maximum number of seeds to generate. Default is no limit. 
When the number of seeds exceeds this number, seeds are chosen 
based on largest internal distance.
"""
        )

        self.structuring_element = cellprofiler.setting.StructuringElement(
            text="Structuring element for seed dilation",
            doc="""\
Structuring element to use for dilating the seeds. 
Volumetric images will require volumetric structuring elements.
"""
        )

        self.max_seeds_per_obj = cellprofiler.setting.Integer(
            text="Maximum number of seeds per object",
            value=0,
            doc="""\
Maximum number of seeds that can be within a single object. Default is
no limit. Depending on the shape of the object and the minimum distance
specified between seeds, a single object might get a number of seeds.
This value enforces a maximum number of seeds that can exist within
a single object (e.g. 1 seed per object).

Note: this may be a slow operation, since it is per-object.
"""
        )

    def settings(self):
        __settings__ = super(SeedObjects, self).settings()

        return __settings__ + [
            self.gaussian_sigma,
            self.min_dist,
            self.min_intensity,
            self.exclude_border,
            self.max_seeds,
            self.structuring_element,
            self.max_seeds_per_obj
        ]

    def visible_settings(self):
        __settings__ = super(SeedObjects, self).visible_settings()

        return __settings__ + [
            self.gaussian_sigma,
            self.min_dist,
            self.min_intensity,
            self.exclude_border,
            self.max_seeds,
            self.max_seeds_per_obj,
            self.structuring_element
        ]

    def run(self, workspace):
        x = workspace.object_set.get_objects(self.x_name.value)

        strel_dim = self.structuring_element.value.ndim

        im_dim = x.segmented.ndim

        # Make sure structuring element matches image dimension
        if strel_dim != im_dim:
            raise ValueError("Structuring element does not match object dimensions: "
                             "{} != {}".format(strel_dim, im_dim))

        self.function = generate_seeds

        super(SeedObjects, self).run(workspace)


def enforce_maximum(labels, seeds, max_seeds_per_obj):
    # Copy the original array in this scope
    seeds = seeds.copy()

    # Label the seeds to get unique labels for each
    labeled_seeds, _ = scipy.ndimage.label(seeds)

    # For each object, enforce the maximum
    # The background (0) shows up in numpy.unique so we trim it out
    for obj in numpy.trim_zeros(numpy.unique(labels)):

        # Get the seeds that are in that object
        obj_mask = seeds & (labels == obj)
        obj_seeds = numpy.trim_zeros(numpy.unique(labeled_seeds * obj_mask))

        # Only proceed if the object has violated the maximum
        num_seeds = len(obj_seeds)
        if num_seeds > max_seeds_per_obj:

            # Get the number of seeds we need to remove to meet the max
            remove_count = num_seeds - max_seeds_per_obj

            # Set up an array that will tell us which we need to remove
            seeds_to_remove = numpy.zeros(num_seeds, dtype=int)
            seeds_to_remove[:remove_count] = 1

            # Randomize which seeds we're going to remove
            numpy.random.shuffle(seeds_to_remove)

            # Get the actual labels of the seeds we need to remove
            labels_to_remove = obj_seeds[numpy.nonzero(obj_seeds * seeds_to_remove)]

            # Remove them from the original seeds array by matching
            # the labels we need to remove to the labeled seeds array
            seeds[numpy.isin(labeled_seeds, labels_to_remove)] = 0

    return seeds


def generate_seeds(labels, gaussian_sigma, distance_threshold, intensity_threshold, border,
                   max_seeds, s_elem, max_seeds_per_obj):
    # Modify settings to correspond to appropriate library defaults
    if max_seeds == -1:
        max_seeds = numpy.inf

    # Pad the image so the distance transform works as expected
    padded = skimage.util.pad(labels, 1, mode='constant', constant_values=0)

    # Compute the distance transform
    seeds = scipy.ndimage.distance_transform_edt(padded)

    # Remove the pad for the next step
    seeds = skimage.util.crop(seeds, 1)

    # Smooth the image
    seeds = skimage.filters.gaussian(seeds, sigma=gaussian_sigma)

    # Generate local peaks
    seeds = skimage.feature.peak_local_max(seeds,
                                           min_distance=distance_threshold,
                                           threshold_rel=intensity_threshold,
                                           exclude_border=border,
                                           num_peaks=max_seeds,
                                           indices=False)

    # Dilate seeds based on settings
    seeds = skimage.morphology.binary_dilation(seeds, s_elem)

    # If user has set a maximum number of seeds per object,
    # enforce said max
    if max_seeds_per_obj > 0:
        seeds = enforce_maximum(labels, seeds, max_seeds_per_obj)

    return seeds


