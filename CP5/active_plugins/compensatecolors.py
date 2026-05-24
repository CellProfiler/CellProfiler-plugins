#################################
#
# Imports from useful Python libraries
#
#################################

import numpy

import scipy.ndimage

import skimage.exposure
import skimage.filters
import skimage.morphology

#################################
#
# Imports from CellProfiler
#
##################################

import cellprofiler_core.image
import cellprofiler_core.module
import cellprofiler_core.setting

__doc__ = """\
CompensateColors
================

**CompensateColors** is a module to deconvolve spectral overlap between at least two sets of images. 
It can optionally be done within an object set.

|

============ ============ ===============
Supports 2D? Supports 3D? Respects masks?
============ ============ ===============
YES          YES          YES
============ ============ ===============


What do I need as input?
^^^^^^^^^^^^^^^^^^^^^^^^

At least two sets of images from which you want to remove spectral overlap.

What do I get as output?
^^^^^^^^^^^^^^^^^^^^^^^^

An equal number of images which have been treated with color compensation.

Technical notes
^^^^^^^^^^^^^^^

Compensation will be performed between compensation classes so you need to assign your images to at least 2 compensation classes.
Often, each compensation class is a separate channel used during image acquisition. 

"""

COMPENSATE_SUFFIX = "Compensated"

CC_IMAGES = "Across entire image"
CC_OBJECTS = "Within objects"


class CompensateColors(cellprofiler_core.module.ImageProcessing):

    module_name = "CompensateColors"

    variable_revision_number = 1

    def create_settings(self):
        self.image_groups = []
        self.add_image(can_delete=False)
        self.spacer_1 = cellprofiler_core.setting.Divider()
        self.add_image(can_delete=False)
        self.spacer_2 = cellprofiler_core.setting.Divider()
        self.add_image_button = cellprofiler_core.setting.do_something.DoSomething(
            "", "Add another image", self.add_image
        )
        self.images_or_objects = cellprofiler_core.setting.choice.Choice(
            "Select where to perform color compensation",
            [CC_IMAGES, CC_OBJECTS],
            doc="""\
    You can measure the correlation in several ways:
    
    -  *%(CC_OBJECTS)s:* Measure correlation only in those pixels previously
       identified as within an object. You will be asked to choose which object
       type to measure within.
    -  *%(CC_IMAGES)s:* Measure the correlation across all pixels in the
       images.

    All methods measure correlation on a pixel by pixel basis.
    """
            % globals(),
        )

        self.object_groups = []
        self.add_object(can_delete=False)
        self.object_count = cellprofiler_core.setting.HiddenCount(self.object_groups)
        self.image_count = cellprofiler_core.setting.HiddenCount(self.image_groups)
        self.do_rescale_input = cellprofiler_core.setting.choice.Choice(
            "Should individual images be rescaled 0-1 before compensating pre-masking or on unmasked images?",
            ["No", "Yes"],
            doc="""\
Choose if the images should be rescaled 0-1 before compensation.
If performing compensation inside an object, rescaling will happen before masking to 
that object""",
        )

        self.do_rescale_after_mask = cellprofiler_core.setting.choice.Choice(
            "Should images be rescaled 0-1 before compensating but after masking to objects?",
            ["No", "Yes, per image", "Yes, per group"],
            doc="""\
Choose if the images should be rescaled 0-1 before compensation; you can choose whether
to do this for each image individually or across all images in a group. 
If performing compensation inside an object, rescaling will happen after masking to 
that object""",
        )

        self.do_match_histograms = cellprofiler_core.setting.choice.Choice(
            "Should histogram matching be performed between the image groups?",
            [
                "No",
                "Yes, pre-masking or on unmasked images",
                "Yes, post-masking to objects",
            ],
            doc="""\
Choose if the images should undergo histogram equalization per group, and when
to perform it if masking inside an object.""",
        )

        self.histogram_match_class = cellprofiler_core.setting.text.Integer(
            "What compensation class should serve as the template histogram?", 1
        )

        self.do_rescale_output = cellprofiler_core.setting.choice.Choice(
            "Should images be rescaled 0-1 after compensating?",
            ["No", "Yes"],
            doc="""\
Choose if the images should be rescaled 0-1 after compensation; you can choose whether
to do this for each image individually or across all images in a group. 
""",
        )

        self.do_scalar_multiply = cellprofiler_core.setting.Binary(
            "Should the images be divided by a scalar based on group percentiles",
            False,
            doc="""\
Choose if per group, the images should have a certain user-defined percentile compared,
and then divided by the ratio between the percentile value of a given group and the 
dimmest group. Example: if the 99th percentile for A, C, G, and T is 0.5, 0.25, 0.3, 
and 0.1, respectively, the pixel values for those groups will be divided by 5, 2.5, 3, 
and 1.  This will be applied before masking or rescaling or histogram compensation.""",
        )

        self.scalar_percentile = cellprofiler_core.setting.text.Float(
            "What percentile should be used for multiplication",
            value=99,
            minval=0.1,
            maxval=100,
            doc="Enter a percentile between 0.1 and 100 to use for comparing ratios",
        )

        self.do_tophat_filter = cellprofiler_core.setting.Binary(
            "Should the images have a tophat filter applied before correction?",
            False,
            doc="""\
Whether or not to apply a tophat filter to enhance small bright spots. This filter will be
applied before rescaling or any other enhancements.""",
        )

        self.tophat_radius = cellprofiler_core.setting.text.Integer(
            "What size radius should be used for the tophat filter?",
            value=3,
            minval=1,
            maxval=100,
            doc="Enter a radius; a disk structuring element of this radius will be used for tophat filtering.",
        )

        self.do_LoG_filter = cellprofiler_core.setting.Binary(
            "Should the images have a Laplacian of Gaussian filter applied before correction?",
            False,
            doc="""\
Whether or not to apply a Laplacian of Gaussian. This filter will be
applied before rescaling or any other enhancements (except tophat filtering if used).""",
        )

        self.LoG_radius = cellprofiler_core.setting.text.Integer(
            "What size radius should be used for the LoG filter?",
            value=1,
            minval=1,
            maxval=100,
            doc="Enter a sigma in pixels; this sigma will be used for LoG filtering.",
        )

        self.do_DoG_filter = cellprofiler_core.setting.Binary(
            "Should the images have a Difference of Gaussians filter applied before correction?",
            False,
            doc="""\
Whether or not to apply a Difference of Gaussians. This filter will be
applied before rescaling or any other enhancements (except tophat filtering and/or LoG filtering if used).""",
        )

        self.DoG_low_radius = cellprofiler_core.setting.text.Integer(
            "What size sigma should be used for the DoG low sigma?",
            value=3,
            minval=1,
            maxval=100,
            doc="Enter a sigma in pixels; this sigma will be used for the lower kernel size.",
        )

        self.DoG_high_radius = cellprofiler_core.setting.text.Integer(
            "What size radius should be used for the DoG low sigma?",
            value=5,
            minval=2,
            maxval=101,
            doc="Enter a sigma in pixels; this sigma will be used for the lower kernel size.",
        )

    def add_image(self, can_delete=True):
        """Add an image to the image_groups collection

        can_delete - set this to False to keep from showing the "remove"
                     button for images that must be present.
        """
        group = cellprofiler_core.setting.SettingsGroup()
        if can_delete:
            group.append("divider", cellprofiler_core.setting.Divider(line=False))
        group.append(
            "image_name",
            cellprofiler_core.setting.subscriber.ImageSubscriber(
                "Select an image to measure",
                "None",
                doc="Select an image to measure the correlation/colocalization in.",
            ),
        )
        group.append(
            "class_num",
            cellprofiler_core.setting.text.Integer(
                "What compensation class does this image belong to?",
                1,
                doc="""\
What compensation class does this image belong to?
You need to divide your images into at least two compensation classes.
Often, each imaging channel is a separate compensation class.""",
            ),
        )
        group.append(
            "output_name",
            cellprofiler_core.setting.text.ImageName(
                "Select an output image name",
                "None",
                doc="What would you like the compensated image to be named?",
            ),
        )
        if (
            len(self.image_groups) == 0
        ):  # Insert space between 1st two images for aesthetics
            group.append("extra_divider", cellprofiler_core.setting.Divider(line=False))

        if can_delete:
            group.append(
                "remover",
                cellprofiler_core.setting.do_something.RemoveSettingButton(
                    "", "Remove this image", self.image_groups, group
                ),
            )

        self.image_groups.append(group)

    def add_object(self, can_delete=True):
        """Add an object to the object_groups collection"""
        group = cellprofiler_core.setting.SettingsGroup()
        if can_delete:
            group.append("divider", cellprofiler_core.setting.Divider(line=False))

        group.append(
            "object_name",
            cellprofiler_core.setting.subscriber.LabelSubscriber(
                "Select an object to perform compensation within",
                "None",
                doc="""\
Select the objects to perform compensation within.""",
            ),
        )

        if can_delete:
            group.append(
                "remover",
                cellprofiler_core.setting.do_something.RemoveSettingButton(
                    "", "Remove this object", self.object_groups, group
                ),
            )
        self.object_groups.append(group)

    def settings(self):
        """Return the settings to be saved in the pipeline"""
        result = [self.image_count, self.object_count]
        for image_group in self.image_groups:
            result += [
                image_group.image_name,
                image_group.class_num,
                image_group.output_name,
            ]
        result += [self.images_or_objects]
        result += [object_group.object_name for object_group in self.object_groups]
        result += [
            self.do_rescale_input,
            self.do_rescale_after_mask,
            self.do_match_histograms,
            self.histogram_match_class,
            self.do_rescale_output,
        ]
        result += [self.do_scalar_multiply, self.scalar_percentile]
        result += [
            self.do_tophat_filter,
            self.tophat_radius,
            self.do_LoG_filter,
            self.LoG_radius,
            self.do_DoG_filter,
            self.DoG_low_radius,
            self.DoG_high_radius,
        ]
        return result

    def prepare_settings(self, setting_values):
        """Make sure there are the right number of image and object slots for the incoming settings"""
        image_count = int(setting_values[0])
        object_count = int(setting_values[1])

        del self.image_groups[image_count:]
        while len(self.image_groups) < image_count:
            self.add_image()

        del self.object_groups[object_count:]
        while len(self.object_groups) < object_count:
            self.add_object()

    def visible_settings(self):
        result = []
        for image_group in self.image_groups:
            result += image_group.visible_settings()
            # result += [image_group.image_name, image_group.class_num, image_group.output_name]
            # if image_group.can_delete:
            # result += [image_group.remover]
        result += [self.add_image_button, self.spacer_2, self.images_or_objects]
        if self.images_or_objects == CC_OBJECTS:
            for object_group in self.object_groups:
                result += object_group.visible_settings()
        result += [self.do_scalar_multiply]
        if self.do_scalar_multiply:
            result += [self.scalar_percentile]
        result += [
            self.do_rescale_input,
            self.do_rescale_after_mask,
            self.do_match_histograms,
        ]
        if self.do_match_histograms != "No":
            result += [self.histogram_match_class]
        result += [self.do_rescale_output]
        result += [self.do_tophat_filter]
        if self.do_tophat_filter:
            result += [self.tophat_radius]
        result += [self.do_LoG_filter]
        if self.do_LoG_filter:
            result += [self.LoG_radius]
        result += [self.do_DoG_filter]
        if self.do_DoG_filter:
            result += [self.DoG_low_radius, self.DoG_high_radius]
        return result

    def run(self, workspace):

        # so far this seems to work best with first masking to objects, then doing 2x2 (A and C, G and T)

        imdict = {}

        sample_image = workspace.image_set.get_image(
            self.image_groups[0].image_name.value
        )
        sample_pixels = sample_image.pixel_data
        sample_shape = sample_pixels.shape

        group_scaling = {}

        if self.do_scalar_multiply.value:
            temp_im_dict = {}
            for eachgroup in self.image_groups:
                eachimage = workspace.image_set.get_image(
                    eachgroup.image_name.value
                ).pixel_data
                if eachgroup.class_num.value not in temp_im_dict.keys():
                    temp_im_dict[eachgroup.class_num.value] = list(eachimage)
                else:
                    temp_im_dict[eachgroup.class_num.value] += list(eachimage)
            for eachclass in temp_im_dict.keys():
                group_scaling[eachclass] = numpy.percentile(
                    temp_im_dict[eachclass], self.scalar_percentile.value
                )
            min_intensity = numpy.min(list(group_scaling.values()))
            for key, value in iter(group_scaling.items()):
                group_scaling[key] = value / min_intensity

        else:
            for eachgroup in self.image_groups:
                if eachgroup.class_num.value not in group_scaling.keys():
                    group_scaling[eachgroup.class_num.value] = 1.0

        if self.images_or_objects.value == CC_OBJECTS:
            object_name = self.object_groups[0]
            objects = workspace.object_set.get_objects(object_name.object_name.value)
            object_labels = objects.segmented
            object_mask = numpy.where(object_labels > 0, 1, 0)

        for eachgroup in self.image_groups:
            eachimage = workspace.image_set.get_image(
                eachgroup.image_name.value
            ).pixel_data

            if self.do_tophat_filter.value:
                selem = skimage.morphology.disk(radius=int(self.tophat_radius.value))
                eachimage = skimage.morphology.white_tophat(eachimage, selem)

            if self.do_LoG_filter.value:
                eachimage = self.log_ndi(eachimage, int(self.LoG_radius.value))

            if self.do_DoG_filter.value:
                eachimage = skimage.filters.difference_of_gaussians(
                    eachimage,
                    int(self.DoG_low_radius.value),
                    int(self.DoG_high_radius.value),
                )

            eachimage = eachimage / group_scaling[eachgroup.class_num.value]
            if self.do_rescale_input.value == "Yes":
                eachimage = skimage.exposure.rescale_intensity(
                    eachimage,
                    in_range=(eachimage.min(), eachimage.max()),
                    out_range=((1.0 / 65535), 1.0),
                )
            if self.do_rescale_after_mask.value == "Yes, per image":
                eachimage = eachimage * object_mask
                eachimage_no_bg = eachimage[
                    eachimage != 0
                ]  # don't measure the background
                eachimage = skimage.exposure.rescale_intensity(
                    eachimage,
                    in_range=(eachimage_no_bg.min(), eachimage_no_bg.max()),
                    out_range=((1.0 / 65535), 1.0),
                )
            eachimage = numpy.round(eachimage * 65535)
            if eachgroup.class_num.value not in imdict.keys():
                imdict[eachgroup.class_num.value] = [
                    [eachgroup.image_name.value],
                    eachimage.reshape(-1),
                    [eachgroup.output_name.value],
                ]
            else:
                imdict[eachgroup.class_num.value][0].append(eachgroup.image_name.value)
                imdict[eachgroup.class_num.value][1] = numpy.concatenate(
                    (imdict[eachgroup.class_num.value][1], eachimage.reshape(-1))
                )
                imdict[eachgroup.class_num.value][2].append(eachgroup.output_name.value)

        keys = list(imdict.keys())
        keys.sort()

        if self.do_match_histograms.value != "No":
            histogram_template = imdict[self.histogram_match_class.value][1]
            if self.do_match_histograms.value == "Yes, post-masking to objects":
                histogram_mask = numpy.tile(
                    object_mask.reshape(-1),
                    len(imdict[self.histogram_match_class.value][0]),
                )
                histogram_template = histogram_mask * histogram_template
                histogram_template = numpy.where(
                    histogram_template == 0, 1, histogram_template
                )

        # apply transformations, if any
        for eachkey in keys:
            reshaped_pixels = imdict[eachkey][1]
            if (
                self.do_match_histograms.value
                == "Yes, pre-masking or on unmasked images"
            ):
                if eachkey != self.histogram_match_class.value:
                    reshaped_pixels = skimage.exposure.match_histograms(
                        reshaped_pixels, histogram_template
                    )
            if self.images_or_objects.value == CC_OBJECTS:
                category_count = len(imdict[eachkey][0])
                category_mask = numpy.tile(object_mask.reshape(-1), category_count)
                reshaped_pixels = reshaped_pixels * category_mask
                reshaped_pixels = numpy.where(reshaped_pixels == 0, 1, reshaped_pixels)
            if self.do_rescale_after_mask.value == "Yes, per group":
                reshaped_pixels_no_bg = reshaped_pixels[
                    reshaped_pixels > 1
                ]  # don't measure the background
                reshaped_pixels = skimage.exposure.rescale_intensity(
                    reshaped_pixels,
                    in_range=(reshaped_pixels_no_bg.min(), reshaped_pixels_no_bg.max()),
                    out_range=(1, 65535),
                )
            if self.do_match_histograms.value == "Yes, post-masking to objects":
                if eachkey != self.histogram_match_class.value:
                    reshaped_pixels = skimage.exposure.match_histograms(
                        reshaped_pixels, histogram_template
                    )
            imdict[eachkey][1] = reshaped_pixels

        imlist = []
        for eachkey in keys:
            imlist.append(imdict[eachkey][1])
        X = numpy.array(imlist)
        X = X.T

        M = self.get_medians(X).T
        M = M / M.sum(axis=0)
        W = numpy.linalg.inv(M)
        Y = W.dot(X.T).astype(int)

        for eachdim in range(Y.shape[0]):
            key = keys[eachdim]
            im_out = Y[eachdim].reshape(
                len(imdict[key][0]), sample_shape[0], sample_shape[1]
            )
            im_out = im_out / 65535.0
            for each_im in range(len(imdict[key][0])):
                im_out[each_im] = numpy.where(im_out[each_im] < 0, 0, im_out[each_im])
                im_out[each_im] = numpy.where(im_out[each_im] > 1, 1, im_out[each_im])
                if self.do_rescale_output.value == "Yes":
                    im_out[each_im] = skimage.exposure.rescale_intensity(
                        im_out[each_im],
                        in_range=(im_out[each_im].min(), im_out[each_im].max()),
                        out_range=(0.0, 1.0),
                    )
                output_image = cellprofiler_core.image.Image(
                    im_out[each_im],
                    parent_image=workspace.image_set.get_image(imdict[key][0][each_im]),
                )
                workspace.image_set.add(imdict[key][2][each_im], output_image)

    #
    # "volumetric" indicates whether or not this module supports 3D images.
    # The "gradient_image" function is inherently 2D, and we've noted this
    # in the documentation for the module. Explicitly return False here
    # to indicate that 3D images are not supported.
    #
    def volumetric(self):
        return False

    def get_medians(self, X):
        arr = []
        for i in range(X.shape[1]):
            arr += [numpy.median(X[X.argmax(axis=1) == i], axis=0)]
        M = numpy.array(arr)
        return M

    def log_ndi(self, data, sigma):
        """ """
        data = skimage.img_as_uint(data)
        f = scipy.ndimage.gaussian_laplace
        arr_ = -1 * f(data.astype(float), sigma)
        arr_ = numpy.clip(arr_, 0, 65535) / 65535

        return skimage.img_as_float(arr_)
