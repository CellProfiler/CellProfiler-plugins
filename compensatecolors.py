# coding=utf-8

#################################
#
# Imports from useful Python libraries
#
#################################

import numpy
import skimage.exposure

#################################
#
# Imports from CellProfiler
#
##################################

import cellprofiler.image
import cellprofiler.module
import cellprofiler.setting

__doc__ = """\
CompensateColors
================

**CompensateColors** is a module to deconvolve spectral overlap between two sets
of images; optionally, this can be done within an object set.

|

============ ============ ===============
Supports 2D? Supports 3D? Respects masks?
============ ============ ===============
YES          YES          YES
============ ============ ===============

See also
^^^^^^^^

Is there another **Module** that is related to this one? If so, refer
to that **Module** in this section. Otherwise, this section can be omitted.

What do I need as input?
^^^^^^^^^^^^^^^^^^^^^^^^

Two sets of images you want to remove spectral overlap from.

What do I get as output?
^^^^^^^^^^^^^^^^^^^^^^^^

An equal number of images which have been treated with color compensation.
As this module can end up running many dozens of images, the output images
will be named by the input name + a user designated suffix, rather than 
manual assignment of each name.


Technical notes
^^^^^^^^^^^^^^^

Include implementation details or notes here. Additionally provide any 
other background information about this module, including definitions
or adopted conventions. Information which may be too specific to fit into
the general description should be provided here.

Omit this section if there is no technical information to mention.

References
^^^^^^^^^^

Provide citations here, if appropriate. Citations are formatted as a list and,
wherever possible, include a link to the original work. For example,

-  Meyer F, Beucher S (1990) “Morphological segmentation.” *J Visual
   Communication and Image Representation* 1, 21-46.
   (`link <http://dx.doi.org/10.1016/1047-3203(90)90014-M>`__)
"""


COMPENSATE_SUFFIX = "Compensated"

CC_IMAGES = "Across entire image"
CC_OBJECTS = "Within objects"

class CompensateColors(cellprofiler.module.ImageProcessing):

    module_name = "CompensateColors"

    variable_revision_number = 1

    def create_settings(self):
        self.image_groups = []
        self.add_image(can_delete=False)
        self.spacer_1 = cellprofiler.setting.Divider()
        self.add_image(can_delete=False)
        self.spacer_2 = cellprofiler.setting.Divider()
        self.add_image_button = cellprofiler.setting.DoSomething("", 'Add another image', self.add_image)
        self.images_or_objects = cellprofiler.setting.Choice(
            'Select where to perform color compensation',
            [
                CC_IMAGES,
                CC_OBJECTS
            ],
            doc="""\
    You can measure the correlation in several ways:
    
    -  *%(CC_OBJECTS)s:* Measure correlation only in those pixels previously
       identified as within an object. You will be asked to choose which object
       type to measure within.
    -  *%(CC_IMAGES)s:* Measure the correlation across all pixels in the
       images.

    All methods measure correlation on a pixel by pixel basis.
    """ % globals()
        )

        self.object_groups = []
        self.add_object(can_delete=False)
        self.object_count = cellprofiler.setting.HiddenCount(self.object_groups)
        self.image_count = cellprofiler.setting.HiddenCount(self.image_groups)
        self.do_rescale_input = cellprofiler.setting.Choice(
            'Should individual images be rescaled 0-1 before compensating?',
            ['No',
            'Yes'],
            doc="""\
Choose if the images should be rescaled 0-1 before compensation.
If performing compensation inside an object, rescaling will happen before masking to 
that object"""
        )

        self.do_match_histograms = cellprofiler.setting.Choice(
            'Should histogram matching be performed between the image groups?',
            ['No',
            'Yes, pre-masking or on unmasked images',
            'Yes, post-masking to objects'],
            doc="""\
Choose if the images should undergo histogram equalization per group, and when
to perform it if masking inside an object."""
        )

        self.histogram_match_class = cellprofiler.setting.Integer(
            'What compensation class should serve as the template histogram?',
            1
        )

        self.do_rescale_output = cellprofiler.setting.Choice(
            'Should images be rescaled 0-1 after compensating?',
            ['No',
            'Yes, per image',
            'Yes, per group'],
            doc="""\
Choose if the images should be rescaled 0-1 after compensation; you can choose whether
to do this for each image individually or across all images in a group. 
"""
        )

    def add_image(self, can_delete=True):
        """Add an image to the image_groups collection

        can_delete - set this to False to keep from showing the "remove"
                     button for images that must be present.
        """
        group = cellprofiler.setting.SettingsGroup()
        if can_delete:
            group.append("divider", cellprofiler.setting.Divider(line=False))
        group.append(
            "image_name",
            cellprofiler.setting.ImageNameSubscriber(
                'Select an image to measure',
                cellprofiler.setting.NONE,
                doc='Select an image to measure the correlation/colocalization in.'
            )
        )
        group.append(
            "class_num",
            cellprofiler.setting.Integer(
                'What compensation class does this image belong to?',
                1
            )
        )
        group.append(
            "output_name",
            cellprofiler.setting.ImageNameProvider(
                'Select an output image name',
                "None"
            )
        )
        if len(self.image_groups) == 0:  # Insert space between 1st two images for aesthetics
            group.append("extra_divider", cellprofiler.setting.Divider(line=False))

        if can_delete:
            group.append("remover", cellprofiler.setting.RemoveSettingButton("", "Remove this image", self.image_groups, group))

        self.image_groups.append(group)

    def add_object(self, can_delete=True):
        """Add an object to the object_groups collection"""
        group = cellprofiler.setting.SettingsGroup()
        if can_delete:
            group.append("divider", cellprofiler.setting.Divider(line=False))

        group.append(
            "object_name",
            cellprofiler.setting.ObjectNameSubscriber(
                'Select an object to perform compensation within',
                cellprofiler.setting.NONE,
                doc="""\
Select the objects to perform compensation within."""
            )
        )

        if can_delete:
            group.append("remover", cellprofiler.setting.RemoveSettingButton('', 'Remove this object', self.object_groups, group))
        self.object_groups.append(group)


    def settings(self):
        """Return the settings to be saved in the pipeline"""
        result = [self.image_count, self.object_count]
        for image_group in self.image_groups:
            result += [image_group.image_name, image_group.class_num, image_group.output_name]
        result += [self.images_or_objects]
        result += [object_group.object_name for object_group in self.object_groups]
        result += [self.do_rescale_input, self.do_match_histograms, self.do_rescale_output]
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
            #result += [image_group.image_name, image_group.class_num, image_group.output_name]
            #if image_group.can_delete:
                #result += [image_group.remover]
        result += [self.add_image_button, self.spacer_2, self.images_or_objects]
        if self.images_or_objects == CC_OBJECTS:
            for object_group in self.object_groups:
                result += object_group.visible_settings()
        result += [self.do_rescale_input, self.do_match_histograms] 
        if self.do_match_histograms != 'No':
            result += [self.histogram_match_class]
        result += [self.do_rescale_output]
        return result

    def run(self, workspace):

        #so far this seems to work best with first masking to objects, then doing 2x2 (A and C, G and T)

        imdict={}

        sample_image = workspace.image_set.get_image(self.image_groups[0].image_name.value)
        sample_pixels = sample_image.pixel_data
        sample_shape = sample_pixels.shape

        if self.images_or_objects.value == CC_OBJECTS:
            object_name = self.object_groups[0]
            objects = workspace.object_set.get_objects(object_name.object_name.value)
            object_labels = objects.segmented
            object_mask = numpy.where(object_labels > 0, 1, 0)

        for eachgroup in self.image_groups:
            eachimage = workspace.image_set.get_image(eachgroup.image_name.value).pixel_data
            if self.do_rescale_input.value == 'Yes':
                eachimage =  skimage.exposure.rescale_intensity(
                    eachimage, 
                    in_range = (eachimage.min(),eachimage.max()),
                    out_range = ((1.0/65535),1.0))
            eachimage = eachimage * 65535
            if eachgroup.class_num.value not in imdict.keys():
                imdict[eachgroup.class_num.value] = [[eachgroup.image_name.value],eachimage.reshape(-1),[eachgroup.output_name.value]]
            else:
                imdict[eachgroup.class_num.value][0].append(eachgroup.image_name.value)
                imdict[eachgroup.class_num.value][1]=numpy.concatenate((imdict[eachgroup.class_num.value][1],eachimage.reshape(-1)))
                imdict[eachgroup.class_num.value][2].append(eachgroup.output_name.value)

        keys=imdict.keys()
        keys.sort()

        if self.do_match_histograms != 'No':
            histogram_template = imdict[self.histogram_match_class.value][1]
            if self.do_match_histograms == 'Yes, post-masking to objects':
                histogram_mask = numpy.tile(object_mask.reshape(-1),len(imdict[self.histogram_match_class.value][0]))
                histogram_template = histogram_mask * histogram_template

        # apply transformations, if any
        for eachkey in keys:
            reshaped_pixels = imdict[eachkey][1]
            if self.do_match_histograms == 'Yes, pre-masking or on unmasked images':
                if eachkey ! = self.histogram_match_class.value:
                    reshaped_pixels = skimage.exposure.match_histograms(reshaped_pixels,histogram_template)
            if self.images_or_objects.value == CC_OBJECTS:
                category_count = len(imdict[keys][0])
                category_mask = numpy.tile(object_mask.reshape(-1),category_count)
                reshaped_pixels = reshaped_pixels * category_mask
                reshaped_pixels = numpy.where(reshaped_pixels == 0, 1, reshaped_pixels)
            if self.do_match_histograms.value == 'Yes, post-masking to objects':
                if eachkey != self.histogram_match_class.value:
                    reshaped_pixels = skimage.exposure.match_histograms(reshaped_pixels,histogram_template)
            imdict[eachkey][1] = reshaped_pixels

        imlist=[]
        for eachkey in keys:
            imlist.append(imdict[eachkey][1])
        X = numpy.array(imlist)
        X = X.T

        M = self.get_medians(X).T
        M = M / M.sum(axis=0)
        W = numpy.linalg.inv(M)
        Y = W.dot(X.T).astype(int)

        for eachdim in range(Y.shape[0]):
            key=keys[eachdim]
            im_out=Y[eachdim].reshape(len(imdict[key][0]),sample_shape[0],sample_shape[1])
            if self.do_rescale_output.value == 'Yes, per group':
                 im_out = skimage.exposure.rescale_intensity(
                     im_out, 
                     in_range = (im_out.min(), im_out.max()),
                     out_range = (0.0,65535.0))
            im_out = im_out / 65535.0
            for each_im in range(len(imdict[key][0])):
                im_out[each_im] = numpy.where(im_out[each_im] < 0, 0, im_out[each_im])
                im_out[each_im] = numpy.where(im_out[each_im] > 1, 1, im_out[each_im])
                if self.do_rescale_output.value == 'Yes, per image':
                    im_out[each_im] = skimage.exposure.rescale_intensity(
                        im_out[each_im], 
                        in_range = (im_out[each_im].min(), im_out[each_im].max()),
                        out_range = (0.0,1.0))
                output_image = cellprofiler.image.Image(im_out[each_im],
                                                        parent_image=workspace.image_set.get_image(imdict[key][0][each_im]))
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

