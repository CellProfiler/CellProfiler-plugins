#################################
#
# Imports from useful Python libraries
#
#################################

import numpy as np

#################################
#
# Imports from CellProfiler
#
##################################

import cellprofiler_core.module as cpm
import cellprofiler_core.setting as cps
from cellprofiler_core.constants.measurement import COLTYPE_FLOAT
from cellprofiler_core.setting.do_something import DoSomething
from cellprofiler_core.setting.subscriber import ImageSubscriber, LabelSubscriber
from cellprofiler_core.utilities.core.object import size_similarly
from centrosome.cpmorphology import fixup_scipy_ndimage_result as fix


__doc__ = """\
CalculateGini
================

**CalculateGini** extracts the Gini coefficient from a given distribution of pixel values.

The user can use all pixels to compute the gini or can restrict to pixels within objects.
If the image has a mask, only unmasked pixels will be used.

Code borrows almost entirely from calculatemoments.py

Available measurements:
- Gini

============ ============ ===============
Supports 2D? Supports 3D? Respects masks?
============ ============ ===============
YES          NO            YES
============ ============ ===============

"""


def get_gini(pixels, labels):
    """For each label, find the corresponding pixels and compute the gini"""
    labs = np.unique(labels)
    gini = np.zeros(np.max(labs) + 1)
    for lab in labs:
        if lab != 0:
            px = pixels[np.where(labels == lab)]
            gini[lab] = get_gini_on_pixels(px)
    return gini[1:]  # skip the 0th value


def get_gini_on_pixels(pixels):
    """Given an array of pixels, get the Gini coefficient

    This entails generating a histogram of pixel values, calculating the CDF,
    and then calculating the Gini coefficient from the CDF.

    Assumes intensties are always positive.
    """
    flattened = np.sort(np.ravel(pixels))
    npix = np.size(flattened)
    normalization = np.abs(np.mean(flattened)) * npix * (npix - 1)
    kernel = (2.0 * np.arange(1, npix + 1) - npix - 1) * np.abs(flattened)

    return np.sum(kernel) / normalization


GINI = "GINI"


class CalculateGini(cpm.Module):

    module_name = "CalculateGini"
    category = "Measurement"
    variable_revision_number = 1

    def create_settings(self):
        """Create the settings for the module at startup."""
        self.image_groups = []
        self.image_count = cps.HiddenCount(self.image_groups)
        self.add_image_cb(can_remove=False)
        self.add_images = DoSomething("", "Add another image", self.add_image_cb)
        self.image_divider = cps.Divider()

        self.object_groups = []
        self.object_count = cps.HiddenCount(self.object_groups)
        self.add_object_cb(can_remove=True)
        self.add_objects = DoSomething("", "Add another object", self.add_object_cb)
        self.object_divider = cps.Divider()

    def settings(self):
        """The settings as they appear in the save file."""
        result = [self.image_count, self.object_count]
        for groups, elements in [
            (self.image_groups, ["image_name"]),
            (self.object_groups, ["object_name"]),
        ]:
            for group in groups:
                for element in elements:
                    result += [getattr(group, element)]
        return result

    def prepare_settings(self, setting_values):
        """Adjust the number of groups based on the number of
        setting_values"""
        for count, sequence, fn in (
            (int(setting_values[0]), self.image_groups, self.add_image_cb),
            (int(setting_values[1]), self.object_groups, self.add_object_cb),
        ):
            del sequence[count:]
            while len(sequence) < count:
                fn()

    def visible_settings(self):
        """The settings as they appear in the module viewer"""
        result = []
        for groups, add_button, div in [
            (self.image_groups, self.add_images, self.image_divider),
            (self.object_groups, self.add_objects, self.object_divider),
        ]:
            for group in groups:
                result += group.visible_settings()
            result += [add_button, div]

        return result

    def add_image_cb(self, can_remove=True):
        """Add an image to the image_groups collection

        can_delete - set this to False to keep from showing the "remove"
                     button for images that must be present.
        """
        group = cps.SettingsGroup()
        if can_remove:
            group.append("divider", cps.Divider(line=False))
        group.append(
            "image_name",
            ImageSubscriber(
                "Select an image to measure",
                "None",
                doc="""What did you call the grayscale images whose Gini you want to calculate?""",
            ),
        )
        if can_remove:
            group.append(
                "remover",
                cps.do_something.RemoveSettingButton(
                    "", "Remove this image", self.image_groups, group
                ),
            )
        self.image_groups.append(group)

    def add_object_cb(self, can_remove=True):
        """Add an object to the object_groups collection

        can_delete - set this to False to keep from showing the "remove"
        button for objects that must be present.
        """
        group = cps.SettingsGroup()
        if can_remove:
            group.append("divider", cps.Divider(line=False))
        group.append(
            "object_name",
            LabelSubscriber(
                "Select objects to measure",
                "None",
                doc="""
                What did you call the objects from which you want to calculate the Gini?
                If you only want to calculate the Gini of the image overall, you can remove
                all objects using the "Remove this object" button. Objects specified here
                will have Gini computed against *all* images specified above, which
                may lead to image-object combinations that are unnecessary. If you
                do not want this behavior, use multiple CalculateGini modules to specify
                the particular image-object measures that you want.""",
            ),
        )
        if can_remove:
            group.append(
                "remover",
                cps.do_something.RemoveSettingButton(
                    "", "Remove this object", self.object_groups, group
                ),
            )
        self.object_groups.append(group)

    def validate_module(self, pipeline):
        """Make sure chosen images are selected only once"""
        images = set()
        for group in self.image_groups:
            if group.image_name.value in images:
                raise cps.ValidationError(
                    "%s has already been selected" % group.image_name.value,
                    group.image_name,
                )
            images.add(group.image_name.value)

        objects = set()
        for group in self.object_groups:
            if group.object_name.value in objects:
                raise cps.ValidationError(
                    "%s has already been selected" % group.object_name.value,
                    group.object_name,
                )
            objects.add(group.object_name.value)

    def run(self, workspace):
        """Run, computing the measurements"""
        statistics = [["Image", "Object", "Measurement", "Value"]]

        for image_group in self.image_groups:
            image_name = image_group.image_name.value
            statistics += self.run_image(image_name, workspace)
            for object_group in self.object_groups:
                object_name = object_group.object_name.value
                statistics += self.run_object(image_name, object_name, workspace)

        if workspace.frame is not None:
            workspace.display_data.statistics = statistics

    def run_image(self, image_name, workspace):
        """Run measurements on image"""
        statistics = []
        input_image = workspace.image_set.get_image(image_name, must_be_grayscale=True)
        pixels = input_image.pixel_data
        gini = get_gini_on_pixels(pixels)
        statistics += self.record_image_measurement(workspace, image_name, "Gini", gini)
        return statistics

    def run_object(self, image_name, object_name, workspace):
        statistics = []
        input_image = workspace.image_set.get_image(image_name, must_be_grayscale=True)
        objects = workspace.get_objects(object_name)
        pixels = input_image.pixel_data
        if input_image.has_mask:
            mask = input_image.mask
        else:
            mask = None
        labels = objects.segmented
        try:
            pixels = objects.crop_image_similarly(pixels)
        except ValueError:
            #
            # Recover by cropping the image to the labels
            #
            pixels, m1 = size_similarly(labels, pixels)
            if np.any(~m1):
                if mask is None:
                    mask = m1
                else:
                    mask, m2 = size_similarly(labels, mask)
                    mask[~m2] = False

        if mask is not None:
            labels = labels.copy()
            labels[~mask] = 0

        # the good stuff
        gini = get_gini(pixels, labels)
        statistics += self.record_measurement(
            workspace, image_name, object_name, "Gini", gini
        )
        return statistics

    def is_interactive(self):
        return False

    def display(self, workspace, figure):
        statistics = workspace.display_data.statistics
        figure.set_subplots((1, 1))
        figure.subplot_table(0, 0, statistics, ratio=(0.25, 0.25, 0.25, 0.25))

    def get_features(self):
        """Return a measurement feature name"""
        return ["Gini"]

    def get_measurement_columns(self, pipeline):
        """Get column names output for each measurement."""
        cols = []
        for im in self.image_groups:
            for feature in self.get_features():
                cols += [
                    (
                        "Image",
                        "%s_%s_%s" % (GINI, feature, im.image_name.value),
                        COLTYPE_FLOAT,
                    )
                ]

        for ob in self.object_groups:
            for im in self.image_groups:
                for feature in self.get_features():
                    cols += [
                        (
                            ob.object_name.value,
                            "%s_%s_%s" % (GINI, feature, im.image_name.value),
                            COLTYPE_FLOAT,
                        )
                    ]

        return cols

    def get_categories(self, pipeline, object_name):
        """Get the measurement categories.

        pipeline - pipeline being run
        image_name - name of images in question
        returns a list of category names
        """
        if any([object_name == og.object_name for og in self.object_groups]):
            return [GINI]
        elif object_name == "Image":
            return [GINI]
        else:
            return []

    def get_measurements(self, pipeline, object_name, category):
        """Get the measurements made on the given image in the given category

        pipeline - pipeline being run
        image_name - name of image being measured
        category - measurement category
        """
        if category in self.get_categories(pipeline, object_name):
            return self.get_features()
        return []

    def get_measurement_images(self, pipeline, object_name, category, measurement):
        """Get the list of images measured

        pipeline - pipeline being run
        image_name - name of objects being measured
        category - measurement category
        measurement - measurement made on images
        """
        if measurement in self.get_measurements(pipeline, object_name, category):
            return [x.image_name.value for x in self.image_groups]
        return []

    def record_measurement(
        self, workspace, image_name, object_name, feature_name, result
    ):
        """Record the result of a measurement in the workspace's
        measurements"""
        data = fix(result)
        data[~np.isfinite(data)] = 0
        workspace.add_measurement(
            object_name, "%s_%s_%s" % (GINI, feature_name, image_name), data
        )
        statistics = [
            [image_name, object_name, feature_name, "%f" % (d) if len(data) else "-"]
            for d in data
        ]
        return statistics

    def record_image_measurement(self, workspace, image_name, feature_name, result):
        """Record the result of a measurement in the workspace's
        measurements"""
        if not np.isfinite(result):
            result = 0
        workspace.measurements.add_image_measurement(
            "%s_%s_%s" % (GINI, feature_name, image_name), result
        )
        statistics = [[image_name, "-", feature_name, "%f" % (result)]]
        return statistics
