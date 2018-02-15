import cellprofiler.module
import cellprofiler.setting
import imagej
import logging

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

        # TODO: Filter modules by headless flag. Server needs to give more info.
        # That said: server should just have a mode for headless-only or not.
        # Then we won't have to detail every module up front anyway.
        return True

    def on_setting_changed(self, setting, pipeline):
        if not setting == self.ij_module:
            return

        self.create_ij_settings(setting.value)

    def create_ij_settings(self, module_name):
        self.ij_settings = cellprofiler.setting.SettingsGroup()

        # Get the module and the module details
        ij = imagej.IJ()
        module = ij.find(module_name)[0]
        details = ij.detail(module)

        # # FOR DEBUGGING
        import json
        logger.debug(json.dumps(details, indent=4))

        for input_ in details["inputs"]:
            name = input_["name"]
            default_value = input_["defaultValue"]
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
                self.ij_settings.append(name, setting)

    def make_setting(self, input_):
        raw_type = input_["rawType"]
        if raw_type in IGNORE_TYPES:
            logger.debug("**** Ignoring input: '" + input_["name"] + "' of type '" + raw_type + "' ****")
            return None

        label = input_["label"]
        text = label if not (label is None or label == "") else input_["name"]
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
            return cellprofiler.setting.Float(text, self.clamp(value, minval), minval, maxval)

        if raw_type in IMAGE_TYPES:
            return cellprofiler.setting.ImageNameSubscriber(text)

        if raw_type in INTEGER_TYPES:
            return cellprofiler.setting.Integer(text, self.clamp(value, minval), minval, maxval)

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

    def clamp(self, value, minval):
        if value:
            return value

        return minval if minval else 0

    # Define settings as instance variables
    # Available settings are in in cellprofiler.settings
    def create_settings(self):
        self.ij_module = cellprofiler.setting.Choice(
            "ImageJ module",
            choices=self.get_ij_modules()
        )

        self.create_ij_settings(self.ij_module.value)

    # Returns the list of available settings
    # This is primarily used to load/save the .cppipe/.cpproj files
    def settings(self):
        settings = [self.ij_module]
        settings += self.ij_settings.settings

        return settings

    def run(self, workspace):
        pass
