#################################
#
# Imports from useful Python libraries
#
#################################

import numpy
import skimage.restoration

#################################
#
# Imports from CellProfiler
#
##################################

__doc__ = """\
RollingBall
===========

**RollingBall*. Because it's past time.

|

============ ============ ===============
Supports 2D? Supports 3D? Respects masks?
============ ============ ===============
YES          NO           YES
============ ============ ===============


"""

#
# Constants
#
# It's good programming practice to replace things like strings with
# constants if they will appear more than once in your program. That way,
# if someone wants to change the text, that text will change everywhere.
# Also, you can't misspell it by accident.
#
from cellprofiler_core.image import Image
from cellprofiler_core.module import ImageProcessing
from cellprofiler_core.setting.text import Integer


class RollingBall(ImageProcessing):

    module_name = "ImageTemplate"

    variable_revision_number = 1

    def create_settings(self):

        super(RollingBall, self).create_settings()

        self.x_name.doc = """\
This is the image that the module operates on. 
"""

        self.radius = Integer(
            text="Ball radius",
            value=10,  # The default value is 1 - a short-range scale
            minval=1,  # We don't let the user type in really small values
            maxval=1000000,  # or large values
            doc="""\
Radius of the ball to use for smoothing
"""
        )

    def settings(self):

        settings = super(RollingBall, self).settings()

        # Append additional settings here.
        return settings + [self.radius]

    def run(self, workspace):

        x_name = self.x_name.value

        y_name = self.y_name.value

        images = workspace.image_set

        x = images.get_image(x_name)

        dimensions = x.dimensions

        x_data = x.pixel_data

        y_data = skimage.restoration.rolling_ball(x_data, radius=self.radius.value)

        y = Image(dimensions=dimensions, image=y_data, parent_image=x)

        images.add(y_name, y)

        if self.show_window:
            workspace.display_data.x_data = x_data

            workspace.display_data.y_data = y_data

            workspace.display_data.dimensions = dimensions

    def volumetric(self):
        return False
