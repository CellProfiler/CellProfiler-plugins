# coding=utf-8

#################################
#
# Imports from useful Python libraries
#
#################################

import numpy

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
    #
    # The module starts by declaring the name that's used for display,
    # the category under which it is stored and the variable revision
    # number which can be used to provide backwards compatibility if
    # you add user-interface functionality later.
    #
    # This module's category is "Image Processing" which is defined
    # by its superclass.
    #
    module_name = "CompensateColors"

    variable_revision_number = 1

    def create_settings(self):
        self.image_groups = []
        self.add_image(can_delete=False)
        self.spacer_1 = cellprofiler.setting.Divider()
        self.add_image(can_delete=False)
        self.spacer_2 = cellprofiler.setting.Divider()
        self.add_image_button = cellprofiler.setting.DoSomething("", 'Add another image', self.add_image)
        self.image_count = cellprofiler.setting.HiddenCount(self.image_groups)
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
        result += [image_group.image_name for image_group in self.image_groups]
        result += [image_group.class_num for image_group in self.image_groups]
        result += [self.images_or_objects]
        result += [object_group.object_name for object_group in self.object_groups]
        return result

    def visible_settings(self):
        result = []
        for image_group in self.image_groups:
            result += image_group.visible_settings()
        result += [self.add_image_button, self.spacer_2, self.images_or_objects]
        if self.images_or_objects == CC_OBJECTS:
            for object_group in self.object_groups:
                result += object_group.visible_settings()
        return result

    def run(self, workspace):

        #so far this seems to work best with first masking to objects, then doing 2x2 (A and C, G and T)
        #consider adding masking functionality

        imdict={}

        sample_image = workspace.image_set.get_image(self.image_groups[0].image_name.value)
        sample_shape = sample_image.shape

        if self.images_or_objects == [CC_OBJECTS]:
            object_name = self.object_groups[0]
            objects = workspace.object_set.get_objects(object_name)
            object_labels = objects.segmented
            object_mask = numpy.where(object_labels > 0, 1, 0)

        else:
            object_mask = numpy.ones_like(self.image_group_a[0])


        for eachgroup in self.image_groups():
            eachimage = workspace.image_set.get_image(eachgroup.image_name.value)
            eachimage = eachimage * object_mask
            eachimage = numpy.where(eachimage == 0, (1/65535), eachimage)
            eachimage = eachimage * 65535
            if eachgroup.class_num not in imdict.keys():
                imdict[eachgroup.class_num] = [[eachgroup.image_name.value],eachimage.reshape(-1)]
            else:
                imdict[eachgroup.class_num][0].append(eachgroup.image_name.value)
                imdict[eachgroup.class_num][1]=numpy.concatenate((imdict[eachgroup.class_num][1],eachimage.reshape(-1)))

        print imdict

        X = numpy.array([imdict[1][1],imdict[2][1]])

        M = self.get_medians(X).T
        M = M / M.sum(axis=0)
        W = numpy.linalg.inv(M)
        Y = W.dot(X.T).T.astype(int)

        Y[0].reshape(len(imdict[1][0]),sample_shape[0],sample_shape[1])
        Y[1].reshape(len(imdict[2][0]),sample_shape[0],sample_shape[1])


    #
    # "volumetric" indicates whether or not this module supports 3D images.
    # The "gradient_image" function is inherently 2D, and we've noted this
    # in the documentation for the module. Explicitly return False here
    # to indicate that 3D images are not supported.
    #
    def volumetric(self):
        return False


    def get_medians(X):
        arr = []
        for i in range(X.shape[1]):
            arr += [numpy.median(X[X.argmax(axis=1) == i], axis=0)]
        M = numpy.array(arr)
        return M

