# coding=utf-8

"""
NucleAIzer
==========

**NucleAIzer** identifies nuclei.

Instructions:

    Warning: For correct usage, this module requires some experience with
    Python and Python dependencies!

    In addition to copying this plugin to your plugins directory, you'll
    need to clone the following Git repository and follow the
    `Prerequisites` instructions in the README:

        https://github.com/spreka/biomagdsb

    This includes installing a specific commit of Matterport's Mask R-CNN
    repository. This plugin _will not_ work with the latest commit! The
    model will not load if the Mask R-CNN modules are not available on your
    Python path since they use custom Keras layers!

    You'll also need to make sure you're running versions of Keras, NumPy,
    SciPy, and TensorFlow that work with `biomagdsb`, `Mask-RCNN`,
    and `CellProfiler`. I had success with the following versions:

        numpy==1.15.4
        scipy==1.1.0
        tensorflow==1.15.0

    Finally, you'll need to download the model configuration and weights:

        https://drive.google.com/drive/folders/1lbJ_LanxSO-n5rMjmhWAHtLcE9znHyJO?usp=sharing
|

============ ============ ===============
Supports 2D? Supports 3D? Respects masks?
============ ============ ===============
YES          NO           YES
============ ============ ===============
"""

import os.path

import numpy
import skimage.measure
import skimage.transform
import tensorflow

import cellprofiler.image
import cellprofiler.module
import cellprofiler.object
import cellprofiler.setting


class IdentifyNucleus(cellprofiler.module.ImageSegmentation):
    category = "Advanced"

    module_name = "IdentifyNucleus"

    variable_revision_number = 1

    def create_settings(self):
        super(IdentifyNucleus, self).create_settings()

        self.mask_name = cellprofiler.setting.ImageNameSubscriber(
            "Mask",
            can_be_blank=True,
            doc=""
        )

        self.model_pathname = cellprofiler.setting.Pathname(
            "Model",
            doc=""
        )

        self.weights_pathname = cellprofiler.setting.Pathname(
            "Weights",
            doc=""
        )

    def settings(self):
        __settings__ = super(IdentifyNucleus, self).settings()

        return __settings__ + [
            self.mask_name,
            self.model_pathname,
            self.weights_pathname
        ]

    def visible_settings(self):
        __settings__ = super(IdentifyNucleus, self).settings()

        __settings__ = __settings__ + [
            self.mask_name,
            self.model_pathname,
            self.weights_pathname
        ]

        return __settings__

    def run(self, workspace):
        model_pathname = os.path.abspath(self.model_pathname.value)

        model = tensorflow.keras.models.model_from_json(model_pathname)

        weights_pathname = os.path.abspath(self.weights_pathname.value)

        model.load_weights(weights_pathname, by_name=True)

        x_name = self.x_name.value
        y_name = self.y_name.value

        images = workspace.image_set

        x = images.get_image(x_name)

        dimensions = x.dimensions

        x_data = x.pixel_data

        x_data = skimage.transform.resize(x_data, (2048, 2048))

        x_data = numpy.expand_dims(x_data, axis=0)

        mask_data = None

        if not self.mask_name.is_blank:
            mask_name = self.mask_name.value

            mask = images.get_image(mask_name)

            mask_data = mask.pixel_data

        prediction = model.predict(x_data)

        _, _, _, predicted_masks, _, _, _ = prediction

        count = predicted_masks.shape[0]

        for index in range(0, count):
            predicted_mask = predicted_masks[index]

            if mask_data:
                predicted_mask *= mask_data

            y_data = skimage.measure.label(predicted_mask)

            objects = cellprofiler.object.Objects()

            objects.segmented = y_data

            objects.parent_image = x

            workspace.object_set.add_objects(objects, y_name)

            self.add_measurements(workspace)

        if self.show_window:
            workspace.display_data.x_data = x.pixel_data

            workspace.display_data.dimensions = dimensions
