# coding=utf-8

"""
RCNN
====

|

============ ============ ===============
Supports 2D? Supports 3D? Respects masks?
============ ============ ===============
YES          NO           YES
============ ============ ===============
"""

import cellprofiler.image
import cellprofiler.module
import cellprofiler.object
import cellprofiler.setting
from tensorflow import keras


class RCNN(cellprofiler.module.ImageSegmentation):
    category = "Advanced"

    module_name = "RCNN"

    variable_revision_number = 1

    def create_settings(self):
        super(RCNN, self).create_settings()

        self.mask_name = cellprofiler.setting.ImageNameSubscriber(
            "Mask",
            can_be_blank=True,
            doc=""
        )

        self.model_pathname = cellprofiler.setting.Pathname("Model", doc="")

    def settings(self):
        __settings__ = super(RCNN, self).settings()

        return __settings__ + [
            self.mask_name,
            self.model_pathname
        ]

    def visible_settings(self):
        __settings__ = super(RCNN, self).settings()

        __settings__ = __settings__ + [
            self.mask_name,
            self.model_pathname
        ]

        return __settings__

    def run(self, workspace):
        model = keras.models.load_model(self.model_pathname.value)

        x_name = self.x_name.value

        y_name = self.y_name.value

        images = workspace.image_set

        x = images.get_image(x_name)

        dimensions = x.dimensions

        x_data = x.pixel_data

        mask_data = None

        if not self.mask_name.is_blank:
            mask_name = self.mask_name.value

            mask = images.get_image(mask_name)

            mask_data = mask.pixel_data

        y_data = x_data

        # y_data = skimage.measure.label(y_data)
        #
        # objects = cellprofiler.object.Objects()
        #
        # objects.segmented = y_data
        #
        # objects.parent_image = x
        #
        # workspace.object_set.add_objects(objects, y_name)
        #
        # self.add_measurements(workspace)

        if self.show_window:
            workspace.display_data.x_data = x.pixel_data

            workspace.display_data.y_data = y_data

            workspace.display_data.dimensions = dimensions
