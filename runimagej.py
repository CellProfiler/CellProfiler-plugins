import cellprofiler.module
import cellprofiler.setting
import imagej


# To start CellProfiler with the plugins directory:
#   `pythonw -m cellprofiler --plugins-directory .`
class RunImageJ(cellprofiler.module.ImageProcessing):
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
        modules = [module.split(".")[-1] for module in modules]
        return modules

    def on_setting_changed(self, setting, pipeline):
        if not setting == self.ijmodule:
            return

        self.create_ijsettings(setting.value)

    def create_ijsettings(self, module_name):
        self.ijsettings = cellprofiler.setting.SettingsGroup()

        # Get the module and the module details
        ij = imagej.IJ()
        module = ij.find(module_name)[0]
        details = ij.detail(module)
        inputs = details["inputs"]

        # # FOR DEBUGGING
        # import json
        # print(json.dumps(details, indent=4))

        for input_ in inputs:
            name = input_["name"]
            default_value = input_["defaultValue"]

            self.ijsettings.append(
                name,
                cellprofiler.setting.Text(name, str(default_value))
            )

    # Define settings as instance variables
    # Available settings are in in cellprofiler.settings
    #
    # The superclass creates the following settings:
    #   - self.x_name: cellprofiler.setting.ImageNameSubscriber, the input image
    #   - self.y_name: cellprofiler.setting.ImageNameProvider, the output image
    def create_settings(self):
        super(RunImageJ, self).create_settings()

        self.ijmodule = cellprofiler.setting.Choice(
            "ImageJ module",
            choices=self.get_ij_modules()
        )

        self.create_ijsettings(self.ijmodule.value)

    # Returns the list of available settings
    # This is primarily used to load/save the .cppipe/.cpproj files
    #
    # The superclass returns:
    #   - [self.x_name, self.y_name]
    def settings(self):
        settings = super(RunImageJ, self).settings()

        settings.append(self.ijmodule)
        settings += self.ijsettings.settings

        return settings

    # Returns a list of settings which are available to the GUI.
    # By default, this is `settings`. Conditional logic can be used
    # to activate and deactivate GUI options.
    def visible_settings(self):
        visible_settings = super(RunImageJ, self).visible_settings()

        visible_settings.append(self.ijmodule)
        visible_settings += self.ijsettings.settings

        return visible_settings

    def run(self, workspace):
        self.function = lambda x: x

        super(RunImageJ, self).run(workspace)
