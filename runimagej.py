import cellprofiler.module


# To start CellProfiler with the plugins directory:
#   `pythonw -m cellprofiler --plugins-directory .`
class RunImageJ(cellprofiler.module.ImageProcessing):
    module_name = "RunImageJ"
    variable_revision_number = 1

    # Define settings as instance variables
    # Available settings are in in cellprofiler.settings
    #
    # The superclass creates the following settings:
    #   - self.x_name: cellprofiler.setting.ImageNameSubscriber, the input image
    #   - self.y_name: cellprofiler.setting.ImageNameProvider, the output image
    def create_settings(self):
        super(RunImageJ, self).create_settings()

    # Returns the list of available settings
    # This is primarily used to load/save the .cppipe/.cpproj files
    #
    # The superclass returns:
    #   - [self.x_name, self.y_name]
    def settings(self):
        settings = super(RunImageJ, self).settings()

        return settings

    # Returns a list of settings which are available to the GUI.
    # By default, this is `settings`. Conditional logic can be used
    # to activate and deactivate GUI options.
    def visible_settings(self):
        visible_settings = super(RunImageJ, self).visible_settings()

        return visible_settings

    def run(self, workspace):
        self.function = lambda x: x

        super(RunImageJ, self).run(workspace)
