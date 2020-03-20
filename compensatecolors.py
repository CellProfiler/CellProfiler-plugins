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
YES          NO           YES
============ ============ ===============

What do I need as input?
^^^^^^^^^^^^^^^^^^^^^^^^

Two sets of images you want to remove spectral overlap from.

What do I get as output?
^^^^^^^^^^^^^^^^^^^^^^^^

An equal number of images which have been treated with color compensation.
As this module can end up running many dozens of images, the output images
will be named by the input name + a user designated suffix, rather than 
manual assignment of each name.

References
^^^^^^^^^^
Optical Pooled Screens in Human Cells.

Feldman D, Singh A, Schmid-Burgk JL, Carlson RJ, Mezger A, Garrity AJ, Zhang F, Blainey PC.

Cell. 2019 Oct 17;179(3):787-799.e17. doi: 10.1016/j.cell.2019.09.016.
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
        self.truncate = cellprofiler.setting.Binary(
            "Set values <0 to 0 and >1 to 1?",
            True,
            doc="""\
Values outside the range 0 to 1 might not be handled well by other
modules. Select *Yes* to set values less than 0 to a minimum of 0 and 
greater than 1 to a maximum value of 1."""
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
        result += [self.truncate]
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
        result += [self.truncate]
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
        else:
            object_mask = numpy.ones_like(sample_pixels)


        for eachgroup in self.image_groups:
            eachimage = workspace.image_set.get_image(eachgroup.image_name.value).pixel_data
            eachimage = eachimage * object_mask
            eachimage = numpy.where(eachimage == 0, (1.0/65535), eachimage)
            eachimage = eachimage * 65535
            if eachgroup.class_num.value not in imdict.keys():
                imdict[eachgroup.class_num.value] = [[eachgroup.image_name.value],eachimage.reshape(-1),[eachgroup.output_name.value]]
            else:
                imdict[eachgroup.class_num.value][0].append(eachgroup.image_name.value)
                imdict[eachgroup.class_num.value][1]=numpy.concatenate((imdict[eachgroup.class_num.value][1],eachimage.reshape(-1)))
                imdict[eachgroup.class_num.value][2].append(eachgroup.output_name.value)

        keys=imdict.keys()
        keys.sort()
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
            im_out = im_out / 65535.
            for each_im in range(len(imdict[key][0])):
                if self.truncate():
                    im_out[each_im] = numpy.where(im_out[each_im] < 0, 0, im_out[each_im])
                    im_out[each_im] = numpy.where(im_out[each_im] > 1, 1, im_out[each_im])
                output_image = cellprofiler.image.Image(im_out[each_im],
                                                        parent_image=workspace.image_set.get_image(imdict[key][0][each_im]))
                workspace.image_set.add(imdict[key][2][each_im], output_image)

    def volumetric(self):
        return False


    def get_medians(self, X):
        arr = []
        for i in range(X.shape[1]):
            arr += [numpy.median(X[X.argmax(axis=1) == i], axis=0)]
        M = numpy.array(arr)
        return M

