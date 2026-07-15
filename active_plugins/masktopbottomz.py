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

__doc__ = """\
MaskTopAndBottomZ
=================

Set planes to ignore/set to all masked in a volumetric binary mask

============ ============ ===============
Supports 2D? Supports 3D? Respects masks?
============ ============ ===============
YES          YES          YES
============ ============ ===============


What do I need as input?
^^^^^^^^^^^^^^^^^^^^^^^^

A binary image

What do I get as output?
^^^^^^^^^^^^^^^^^^^^^^^^

A binary image, with the top and/or bottom all masked out


"""

from cellprofiler_core.image import Image
from cellprofiler_core.module import ImageProcessing
from cellprofiler_core.setting.text import Integer



class MaskTopBottomZ(ImageProcessing):

    module_name = "MaskTopAndBottomZ"

    variable_revision_number = 1

    def create_settings(self):

        super(MaskTopBottomZ, self).create_settings()

        #
        # reST help that gets displayed when the user presses the
        # help button to the right of the edit box.
        #
        # The superclass defines some generic help test. You can add
        # module-specific help text by modifying the setting's "doc"
        # string.
        #
        self.x_name.doc = """\
This is the image that the module operates on. You can choose any image
that is made available by a prior module.

**ImageTemplate** will do something to this image.
"""


        self.bottom_remove = Integer(
            text="Planes from the bottom to remove?",
            value=0,  
            doc="""\
Planes to remove from the lowest-number-Z-plane side of the image
""",
        )

        self.top_remove = Integer(
            text="Planes from the top to remove?",
            value=0,  
            doc="""\
Planes to remove from the highest-number-Z-plane side of the image
""",
        )

    def settings(self):

        settings = super(MaskTopBottomZ, self).settings()

        return settings + [self.bottom_remove, self.top_remove]


    def visible_settings(self):

        visible_settings = super(MaskTopBottomZ, self).visible_settings()

        visible_settings += [self.bottom_remove, self.top_remove]

        return visible_settings


    def run(self, workspace):

        try:
            binary_image = workspace.image_set.get_image(
                        self.x_name.value, must_be_binary=True
                    )
            binary_pixels = binary_image.pixel_data
        except ValueError:
            binary_image = workspace.image_set.get_image(
                        self.x_name.value, must_be_grayscale=True
                    )
            binary_pixels = binary_image.pixel_data
            binary_pixels = binary_pixels > 0.5
        
        if not binary_image.volumetric:
            raise Exception("This module can only be used for volumetric images")
        
        number_planes = binary_pixels.shape[0]

        if self.bottom_remove.value + self.top_remove.value > number_planes:
            raise Exception("You are removing more planes than the image has")
        
        binary_pixels[:self.bottom_remove.value,:,:] = False

        binary_pixels[-self.top_remove.value:,:,:] = False

        y = Image(dimensions=binary_image.dimensions, image=binary_pixels, parent_image=binary_image)

        workspace.image_set.add(self.y_name.value, y)

        if self.show_window:
            workspace.display_data.x_data = binary_image.pixel_data

            workspace.display_data.y_data = binary_pixels

            workspace.display_data.dimensions = binary_image.dimensions

    def volumetric(self):
        return True

