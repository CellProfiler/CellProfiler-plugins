import os.path
import logging

import cellprofiler.measurement
import cellprofiler.module
import cellprofiler.preferences
import cellprofiler.setting
import microscopeimagequality.miq
import microscopeimagequality.prediction
import matplotlib.cm
import matplotlib.pyplot
import matplotlib.patches

__doc__ = """
For installation instructions and platform support notes, please see the `wiki <https://github.com/CellProfiler/CellProfiler-plugins/wiki/Measure-Image-Focus/>`_.

This module can collect measurements indicating possible image aberrations,
e.g. blur (poor focus), intensity, saturation (i.e., the percentage
of pixels in the image that are minimal and maximal).
It outputs an image focus score, an integer from 0 (in focus) to 10 (out of focus).
There is also a certainty output indicating how certain the score is.
"""

C_IMAGE_FOCUS = "ImageFocus"
F_SCORE = "Score"
F_CERTAINTY = "Certainty"

class MeasureImageFocus(cellprofiler.module.Module):
    category = "Measurement"

    module_name = "MeasureImageFocus"

    variable_revision_number = 1

    def create_settings(self):
        self.image_name = cellprofiler.setting.ImageNameSubscriber(
                "Image",
                doc="""
            The name of an image.
            """
        )

    def settings(self):
        return [
            self.image_name
        ]

    def display(self, workspace, figure):

        figure.set_subplots((2, 1))

        patches= workspace.display_data.patches

        figure.subplot_table(0, 0, workspace.display_data.statistics)
        image = workspace.display_data.image

        ax = figure.subplot_imshow_grayscale(1, 0, image,
                                title="Focus Score"
                             )
        # show patches
        cmap = matplotlib.cm.jet
        for patch in patches:
            rect = matplotlib.patches.Rectangle(xy=(patch[1], patch[0]), width=patch[3], height=patch[2])
            rect.set_color(cmap(int(float(patch[4][0]) * 255 / 10)))
            rect.set_alpha(float(patch[4][1]['aggregate']) * 0.9)
            rect.set_linewidth(0)
            rect.set_fill(True)
            ax.add_patch(rect)

        # colorbar
        sm = matplotlib.pyplot.cm.ScalarMappable(cmap=cmap, norm=matplotlib.pyplot.Normalize(vmin=0, vmax=10))
        sm.set_array([])
        cbar = matplotlib.pyplot.colorbar(sm, ax=ax, ticks=[0, 10], shrink=.6)
        cbar.ax.set_yticklabels(['Focused', 'Unfocused'])

    def get_categories(self, pipeline, object_name):
        if object_name == cellprofiler.measurement.IMAGE:
            return [
                C_IMAGE_FOCUS
            ]

        return []

    def get_feature_name(self, name):
        image = self.image_name.value

        return C_IMAGE_FOCUS + "_{}_{}".format(name, image)

    def get_measurements(self, pipeline, object_name, category):
        name = self.image_name.value

        if object_name == cellprofiler.measurement.IMAGE and category == C_IMAGE_FOCUS:
            return [
                F_SCORE + "_{}".format(name),
                F_CERTAINTY + "_{}".format(name)
            ]

        return []

    def get_measurement_columns(self, pipeline):
        image = cellprofiler.measurement.IMAGE

        features = [
            self.get_feature_name(F_SCORE),
            self.get_feature_name(F_CERTAINTY)
        ]

        column_type = cellprofiler.measurement.COLTYPE_FLOAT

        return [(image, feature, column_type) for feature in features]

    def get_measurement_images(self, pipeline, object_name, category, measurement):
        if measurement in self.get_measurements(pipeline, object_name, category):
            return [self.image_name.value]

        return []

    def run(self, workspace):
        default_weights_index_file = microscopeimagequality.miq.DEFAULT_MODEL_PATH + '.index'
        if not os.path.exists(default_weights_index_file):
            logging.warning('weights index file not found at {}'.format(default_weights_index_file))
            microscopeimagequality.miq.download_model()

        m = microscopeimagequality.prediction.ImageQualityClassifier(microscopeimagequality.miq.DEFAULT_MODEL_PATH, 84,
                                                                     11)

        image_set = workspace.image_set
        image = image_set.get_image(self.image_name.value, must_be_grayscale=True)

        data = image.pixel_data

        measurements = workspace.measurements

        statistics = []

        pred = m.predict(data)
        patches = m.get_patch_predictions(data)

        feature_score = self.get_feature_name(F_SCORE)
        score = str(pred[0])
        feature_certainty = self.get_feature_name(F_CERTAINTY)
        certainty = str(pred[1]['aggregate'])

        statistics.append([feature_score, score])
        statistics.append([feature_certainty, certainty])

        measurements.add_image_measurement(feature_score, score)
        measurements.add_image_measurement(feature_certainty, certainty)

        # if self.show_window:
        workspace.display_data.statistics = statistics
        workspace.display_data.patches = patches
        workspace.display_data.image= data

    def volumetric(self):
        return False
