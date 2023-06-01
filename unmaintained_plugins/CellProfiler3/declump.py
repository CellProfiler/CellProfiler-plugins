# coding=utf-8

"""
DeclumpObjects
==============

**DeclumpObjects** will split objects based on a seeded watershed method

#. Compute the `local maxima`_ (either through the `Euclidean distance transformation`_
of the segmented objects or through the intensity values of a reference image

#. Dilate the seeds as specified

#. Use these seeds as markers for watershed

NOTE: This implementation is based off of the **IdentifyPrimaryObjects** declumping implementation.
For more information, see the aforementioned module.

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
import skimage.morphology
import skimage.segmentation
import scipy.ndimage
import skimage.filters
import skimage.feature
import skimage.util

import cellprofiler.image
import cellprofiler.module
import cellprofiler.setting
import cellprofiler.object


O_SHAPE = "Shape"
O_INTENSITY = "Intensity"


class DeclumpObjects(cellprofiler.module.ObjectProcessing):
    category = "Advanced"

    module_name = "DeclumpObjects"

    variable_revision_number = 1

    def create_settings(self):
        super(DeclumpObjects, self).create_settings()

        self.declump_method = cellprofiler.setting.Choice(
            text="Declump method",
            choices=[O_SHAPE, O_INTENSITY],
            value=O_SHAPE,
            doc="""\
This setting allows you to choose the method that is used to draw the
line between segmented objects. 

-  *{O_SHAPE}:* Dividing lines between clumped objects are based on
   the shape of the clump. For example, when a clump contains two
   objects, the dividing line will be placed where indentations occur
   between the two objects. The intensity of the original image is
   not necessary in this case. 
   
   **Technical description:** The distance transform of the segmentation 
   is used to identify local maxima as seeds (i.e. the centers of the 
   individual objects), and the seeds are then used on the inverse of 
   that distance transform to determine new segmentations via watershed.

-  *{O_INTENSITY}:* Dividing lines between clumped objects are determined
   based on the intensity of the original image. This works best if the
   dividing line between objects is dimmer than the objects themselves.

   **Technical description:** The distance transform of the segmentation 
   is used to identify local maxima as seeds (i.e. the centers of the 
   individual objects). Those seeds are then used as markers for a 
   watershed on the inverted original intensity image.
""".format(**{
                "O_SHAPE": O_SHAPE,
                "O_INTENSITY": O_INTENSITY
            })
        )

        self.reference_name = cellprofiler.setting.ImageNameSubscriber(
            text="Reference Image",
            doc="Image to reference for the *{O_INTENSITY}* method".format(**{"O_INTENSITY": O_INTENSITY})
        )

        self.gaussian_sigma = cellprofiler.setting.Float(
            text="Segmentation distance transform smoothing factor",
            value=1.,
            doc="Sigma defines how 'smooth' the Gaussian kernel makes the image. Higher sigma means a smoother image."
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
            doc="""\
Minimum absolute intensity threshold for seed generation. Since this threshold is
applied to the distance transformed image, this defines a minimum object
"size". Objects smaller than this size will not contain seeds. 

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

        self.connectivity = cellprofiler.setting.Integer(
            text="Watershed connectivity",
            value=1,
            minval=1,
            maxval=3,
            doc="Connectivity for the watershed algorithm. Default is 1, maximum is number of dimensions of the image"
        )

    def settings(self):
        __settings__ = super(DeclumpObjects, self).settings()

        return __settings__ + [
            self.declump_method,
            self.reference_name,
            self.gaussian_sigma,
            self.min_dist,
            self.min_intensity,
            self.exclude_border,
            self.max_seeds,
            self.structuring_element,
            self.connectivity
        ]

    def visible_settings(self):
        __settings__ = super(DeclumpObjects, self).visible_settings()

        __settings__ += [self.declump_method]

        if self.declump_method.value == O_INTENSITY:
            __settings__ += [self.reference_name]

        __settings__ += [
            self.gaussian_sigma,
            self.min_dist,
            self.min_intensity,
            self.exclude_border,
            self.max_seeds,
            self.structuring_element,
            self.connectivity
        ]

        return __settings__

    def run(self, workspace):
        x_name = self.x_name.value
        y_name = self.y_name.value
        object_set = workspace.object_set
        images = workspace.image_set

        x = object_set.get_objects(x_name)
        x_data = x.segmented

        strel_dim = self.structuring_element.value.ndim

        im_dim = x.segmented.ndim

        # Make sure structuring element matches image dimension
        if strel_dim != im_dim:
            raise ValueError("Structuring element does not match object dimensions: "
                             "{} != {}".format(strel_dim, im_dim))

        # Get the segmentation distance transform
        peak_image = scipy.ndimage.distance_transform_edt(x_data > 0)

        # Generate a watershed ready image
        if self.declump_method.value == O_SHAPE:
            # Use the reverse of the image to get basins at peaks
            # dist_transform = skimage.util.invert(dist_transform)
            watershed_image = -peak_image
            watershed_image -= watershed_image.min()

        else:
            reference_name = self.reference_name.value
            reference = images.get_image(reference_name)
            reference_data = reference.pixel_data

            # Set the image as a float and rescale to full bit depth
            watershed_image = skimage.img_as_float(reference_data, force_copy=True)
            watershed_image -= watershed_image.min()
            watershed_image = 1 - watershed_image

        # Smooth the image
        watershed_image = skimage.filters.gaussian(watershed_image, sigma=self.gaussian_sigma.value)

        # Generate local peaks
        seeds = skimage.feature.peak_local_max(peak_image,
                                               min_distance=self.min_dist.value,
                                               threshold_rel=self.min_intensity.value,
                                               exclude_border=self.exclude_border.value,
                                               num_peaks=self.max_seeds.value if self.max_seeds.value != -1 else numpy.inf,
                                               indices=False)

        # Dilate seeds based on settings
        seeds = skimage.morphology.binary_dilation(seeds, self.structuring_element.value)
        seeds_dtype = (numpy.int16 if x.count < numpy.iinfo(numpy.int16).max else numpy.int32)

        # NOTE: Not my work, the comments below are courtesy of Ray
        #
        # Create a marker array where the unlabeled image has a label of
        # -(nobjects+1)
        # and every local maximum has a unique label which will become
        # the object's label. The labels are negative because that
        # makes the watershed algorithm use FIFO for the pixels which
        # yields fair boundaries when markers compete for pixels.
        #
        seeds = scipy.ndimage.label(seeds)[0]

        markers = numpy.zeros_like(seeds, dtype=seeds_dtype)
        markers[seeds > 0] = -seeds[seeds > 0]

        # Perform the watershed
        watershed_boundaries = skimage.morphology.watershed(
            connectivity=self.connectivity.value,
            image=watershed_image,
            markers=markers,
            mask=x_data != 0
        )

        y_data = watershed_boundaries.copy()
        # Copy the location of the "background"
        zeros = numpy.where(y_data == 0)
        # Re-shift all of the labels into the positive realm
        y_data += numpy.abs(numpy.min(y_data)) + 1
        # Re-apply the background
        y_data[zeros] = 0

        objects = cellprofiler.object.Objects()
        objects.segmented = y_data.astype(numpy.uint16)
        objects.parent_image = x.parent_image

        object_set.add_objects(objects, y_name)

        self.add_measurements(workspace)

        if self.show_window:
            workspace.display_data.x_data = x.segmented

            workspace.display_data.y_data = y_data

            workspace.display_data.dimensions = x.dimensions
