# Troubleshooting

| Problem | Solution | 
|---|-----|
| After setting the CellProfiler Plugins folder, CellProfiler won't open and returns an `error: no commands supplied` in the terminal. | You have set the CellProfiler Plugins folder to the parent folder of the plugins repository (`CellProfiler-plugins`), not the folder that contains plugins (`CellProfiler-plugins/active_plugins`). In order to get it to open, remove `setup.py` from the folder. Change the CellProfiler Plugins path to the correct path and close CellProfiler. Return `setup.py` to the parent folder. |
| No plugins are visible in the "Add Modules" panel in CellProfiler. | You have not properly set the plugins path. Go to `CellProfiler` => `Preferences` and set the path in the `CellProfiler plugins directory` to the `active_plugins` folder in the GitHub repository that you just cloned. Select `Save` at the bottom of the Preferences window. |
| Some but not all plugins are visible in the in the "Add Modules" panel in CellProfiler. | Not-visible plugins have unmet dependencies. Follow [installation instructions](using_plugins.md) to install dependencies for plugins. |