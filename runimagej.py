# coding=utf-8

import StringIO
import json
import logging
import tempfile

import cellprofiler.image
import cellprofiler.module
import cellprofiler.setting
import imagej
import numpy as np
import skimage.io
from PIL import Image

# TODO:
# - Saving and loading pipeline does not preserve module-specific settings.
# - Current implementation requires the server to be started. Appears to wait
#   indefinitely if there is not a server running at the configured location.
#   There should be a time out.
# - The running server seems to conflict with CellProfiler's JVM? Cannot load
#   images, presumably because of conflict with python-bioformats/javabridge.
#   Though this seems somewhat weird, because you should be able to run two
#   JVMs in different processes, right?

logger = logging.getLogger(__name__)

BOOL_TYPES = [
    "boolean",
    "java.lang.Boolean"
]

COLOR_TYPES = ["org.scijava.util.ColorRGB"]

FILE_TYPES = ["java.io.File"]

FLOAT_TYPES = [
    "double",
    "float",
    "java.lang.Double",
    "java.lang.Float",
    "java.math.BigDecimal"
]

IGNORE_TYPES = [
    "org.scijava.widget.Button"  # For now!
]

IMAGE_TYPES = [
    "net.imagej.Dataset",
    "net.imagej.display.DataView",
    "net.imagej.display.DatasetView",
    "net.imagej.display.ImageDisplay",
    "net.imglib2.IterableInterval",
    "net.imglib2.RandomAccessibleInterval",
    "net.imglib2.img.*Img"
]

INTEGER_TYPES = [
    "byte",
    "int",
    "long",
    "short",
    "java.lang.Byte",
    "java.lang.Integer",
    "java.lang.Long",
    "java.lang.Short",
    "java.math.BigInteger"
]

TEXT_TYPES = [
    "char",
    "java.lang.Character",
    "java.lang.String",
    "java.util.Date"
]

# To start CellProfiler with the plugins directory:
#   `pythonw -m cellprofiler --plugins-directory .`
class RunImageJ(cellprofiler.module.Module):
    category = "Advanced"
    module_name = "RunImageJ"
    variable_revision_number = 1

    @staticmethod
    def get_ij_modules():
        # TODO: configure the ImageJ server host in CellProfiler's preferences.
        # Not sure we can do this via CellProfiler-plugins but maaaaaybeeee?
        # Otherwise, we'll need to expose this via a setting or an env variable.
        #
        # I tried exposing this through a setting and calling on_setting_changed
        # when the host was updated; on_setting_change would repopulate the
        # module choices using this method. However, there isn't a choices setter
        # on the Choice setting. :(
        ij = imagej.IJ()
        modules = ij.modules()
        modules = [module.split(".")[-1] for module in modules if RunImageJ.is_friendly_module(module)]
        return sorted(modules)

    @staticmethod
    def is_friendly_module(module):
        # HACK: Filter out nastily long and useless modules.
        if module.startswith('command:net.imagej.plugins.commands.misc.ApplyLookupTable(') or \
                module.startswith('command:org.scijava.plugins.commands.io.OpenFile('):
            return False

        return True

    def on_setting_changed(self, setting, pipeline):
        if not setting == self.ij_module:
            return

        self.create_ij_settings(setting.value)

    def create_ij_settings(self, module_name):
        self.inputs = []
        self.input_settings = cellprofiler.setting.SettingsGroup()

        self.outputs = []
        self.output_settings = cellprofiler.setting.SettingsGroup()

        ij = imagej.IJ()
        module = ij.find(module_name)[0]
        details = ij.detail(module)

        # FOR DEBUGGING
        logger.debug(json.dumps(details, indent=4))

        for input_ in details["inputs"]:
            name = input_["name"]
            input_["rawType"] = raw_type = input_["genericType"].split("<")[0].split(" ")[-1]

            # HACK: For now, we skip service and context parameters.
            # Later, the ImageJ Server will filter these out for us.
            if raw_type.endswith("Service") or raw_type == "org.scijava.Context":
                continue

            # TODO:
            # - Exclude inappropriate visibilities
            #   But ImageJ server does not tell us right now
            # - Add outputs

            setting = self.make_setting(input_)
            if setting is not None:
                self.inputs.append(input_)
                self.input_settings.append(name, setting)

        for output in details["outputs"]:
            raw_type = output["genericType"].split("<")[0].split(" ")[-1]
            output['rawType'] = raw_type
            if raw_type in IMAGE_TYPES:
                label = output["label"]
                text = label if label and not label == "" else output["name"]
                setting = cellprofiler.setting.ImageNameProvider(text)
                self.outputs.append(output)
                self.output_settings.append("output_" + output["name"], setting)

    def make_setting(self, input_):
        raw_type = input_["rawType"]
        if raw_type in IGNORE_TYPES:
            logger.debug("**** Ignoring input: '" + input_["name"] + "' of type '" + raw_type + "' ****")
            return None

        label = input_["label"]
        text = label if label and not label == "" else input_["name"]
        value = input_["defaultValue"]
        minval = input_["minimumValue"]
        maxval = input_["maximumValue"]
        style = input_["widgetStyle"].lower()

        if raw_type in BOOL_TYPES:
            return cellprofiler.setting.Binary(text, value)

        if raw_type in COLOR_TYPES:
            return cellprofiler.setting.Color(text, value)

        if raw_type in FILE_TYPES:
            if style.startswith("directory"):
                # TODO: Massage non-None value to CellProfiler-friendly string.
                return cellprofiler.setting.DirectoryPath(text)

            # "open" or "save" or unspecified
            # TODO: Use a fancier combination of widgets.
            return cellprofiler.setting.Pathname(text, value if value else '')

        if raw_type in FLOAT_TYPES:
            return cellprofiler.setting.Float(text, self._clamp(value, minval), minval, maxval)

        if raw_type in IMAGE_TYPES:
            return cellprofiler.setting.ImageNameSubscriber(text)

        if raw_type in INTEGER_TYPES:
            return cellprofiler.setting.Integer(text, self._clamp(value, minval), minval, maxval)

        if raw_type in TEXT_TYPES:
            choices = input_["choices"]
            if choices is None:
                if style.startswith("text area"):
                    return cellprofiler.setting.Text(text, value, multiline=True)
                return cellprofiler.setting.Text(text, value)

            return cellprofiler.setting.Choice(text, choices)

        # TODO: handle error somehow -- maybe put a label saying "unsupported input: blah"
        logger.debug("**** Unsupported input: '" + input_["name"] + "' of type '" + raw_type + "' ****")
        return None

    # Define settings as instance variables
    # Available settings are in in cellprofiler.settings
    def create_settings(self):
        self.ij_module = cellprofiler.setting.Choice(
            "ImageJ module",
            choices=self.get_ij_modules()
        )

        self.divider = cellprofiler.setting.Divider(u"———OUTPUTS———")

        self.create_ij_settings(self.ij_module.value)

    # Returns the list of available settings
    # This is primarily used to load/save the .cppipe/.cpproj files
    def settings(self):
        settings = [
            self.ij_module,
            self.divider
        ]

        settings += self.input_settings.settings
        settings += self.output_settings.settings

        return settings

    def visible_settings(self):
        visible_settings = [self.ij_module]
        visible_settings += self.input_settings.settings

        if len(self.output_settings.settings) > 0:
            visible_settings.append(self.divider)
            visible_settings += self.output_settings.settings

        return visible_settings

    def run(self, workspace):
        ij = imagej.IJ()
        # FIXME: Keep the original IDs in some data structure,
        # so that we guarantee we run the correct module here.
        id = ij.find(self.ij_module.value)[0]
        inputs = {}

        if self.show_window:
            workspace.display_data.images = []

        # Harvest the inputs.
        for details, setting in zip(self.inputs, self.input_settings.settings):
            name = details["name"]
            value = self._input_value(setting, workspace)

            # Remember input images if they should be shown.
            if isinstance(setting, cellprofiler.setting.ImageNameSubscriber):
                if self.show_window:
                    workspace.display_data.images.append(value)

                # Upload the image to the server.
                with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
                    skimage.io.imsave(tmp.name, value)
                    img_id = ij.upload(tmp.name)
                    inputs[name] = img_id

            else:
                inputs[name] = value

        # Run the module.
        result = ij.run(id, inputs, True)

        # Populate the outputs.
        for details, setting in zip(self.outputs, self.output_settings.settings):
            value = self._output_value(setting, result[details["name"]], ij)

            # Record output images if they should be shown.
            if isinstance(setting, cellprofiler.setting.ImageNameProvider):
                image = cellprofiler.image.Image(value)
                workspace.image_set.add(setting.value, image)
                if self.show_window:
                    workspace.display_data.images.append(value)

    def display(self, workspace, figure):
        image_count = len(workspace.display_data.images)
        figure.set_subplots((image_count, 1))
        for idx, image in enumerate(workspace.display_data.images):
            figure.subplot_imshow(idx, 0, image)

    def _input_value(self, setting, workspace):
        if isinstance(setting, cellprofiler.setting.ImageNameSubscriber):
            return workspace.image_set.get_image(setting.value).pixel_data

        return setting.value

    def _output_value(self, setting, id, ij):
        if isinstance(setting, cellprofiler.setting.ImageNameProvider):
            data = ij.retrieve(id, format='png')
            pil = Image.open(StringIO.StringIO(data))
            return np.array(pil)

        logger.debug("**** Unsupported output: '" + id + "' ****")
        return None

    def _clamp(self, value, minval):
        if value:
            return value

        return minval if minval else 0

