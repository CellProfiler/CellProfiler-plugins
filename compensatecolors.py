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

        super(CompensateColors, self).create_settings()
        self.image_group_a = cellprofiler.setting.SettingsGroup()
        self.add_image(self.image_group_a, can_delete=False)
        self.spacer_1 = cellprofiler.setting.Divider()
        self.add_image_button = cellprofiler.setting.DoSomething("", 'Add another image', self.add_image(self.image_group_a))
        self.spacer_2 = cellprofiler.setting.Divider(line=True)
        self.image_a_count = cellprofiler.setting.HiddenCount(self.image_group_a)

        self.image_group_b = cellprofiler.setting.SettingsGroup()
        self.add_image(self.image_group_b, can_delete=False)
        self.spacer_3 = cellprofiler.setting.Divider()
        self.add_image_button = cellprofiler.setting.DoSomething("", 'Add another image', self.add_image(self.image_group_b))
        self.spacer_4 = cellprofiler.setting.Divider(line=True)
        self.image_b_count = cellprofiler.setting.HiddenCount(self.image_group_b)



        self.images_or_objects = cellprofiler.setting.Choice(
            'Select where to perform color compensation',
            [
                CC_IMAGES,
                CC_OBJECTS
            ],
            doc="""\
    You can measure the correlation in several ways:
    
    -  *%(M_OBJECTS)s:* Measure correlation only in those pixels previously
       identified as within an object. You will be asked to choose which object
       type to measure within.
    -  *%(M_IMAGES)s:* Measure the correlation across all pixels in the
       images.

    All methods measure correlation on a pixel by pixel basis.
    """ % globals()
        )

        self.object_groups = []
        self.add_object(can_delete=False)
        self.object_count = cellprofiler.setting.HiddenCount(self.object_groups)

        self.spacer_2 = cellprofiler.setting.Divider(line=True)

    def add_image(self, group, can_delete=True):
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
                'Select an object to measure',
                cellprofiler.setting.NONE,
                doc="""\
*(Used only when "Within objects" or "Both" are selected)*

Select the objects to be measured."""
            )
        )

        if can_delete:
            group.append("remover", cellprofiler.setting.RemoveSettingButton('', 'Remove this object', self.object_groups, group))
        self.object_groups.append(group)


    def visible_settings(self):

        visible_settings = super(CompensateColors, self).visible_settings()

        # Configure the visibility of additional settings below.
        visible_settings += [
            self.gradient_choice,
            self.automatic_smoothing
        ]

        return visible_settings

    def run(self, workspace):

        #so far this seems to work best with first masking to objects, then doing 2x2 (A and C, G and T)
        #consider adding masking functionality

        t=numpy.concatenate((im1,im2))

        M = t * 65535

        M = self.get_medians(X).T
        M = M / M.sum(axis=0)
        W = numpy.linalg.inv(M)
        Y = W.dot(X.T).T.astype(int)

        Y[0].reshape(nimages,xsize,ysize)
        Y[1].reshape(nimages,xsize,ysize)



        super(ImageTemplate, self).run(workspace)

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

