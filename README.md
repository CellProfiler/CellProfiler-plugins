# CellProfiler-plugins

A home for community-contributed, experimental, and dependency-heavy CellProfiler modules. 

Plugins advance the capabilities of CellProfiler but are not officially supported in the same way as modules.
A module may be in CellProfiler-plugins instead of CellProfiler itself because:
- it is under active development
- it has a niche audience
- it is not documented to CellProfiler's standards
- it only works with certain version of CellProfiler
- it requires extra libraries or other dependencies we are unable or unwilling to require for CellProfiler
- it has been contributed by a community member

Please see our [CellProfiler-plugins documentation](https://plugins.cellprofiler.org) for more information about installation, currently supported plugins, and how to contribute.

## Troubleshooting

If CellProfiler won't open after setting the CellProfiler Plugins folder (and it returns `error: no commands supplied` in the terminal), it is likely because you have set the CellProfiler Plugins folder to the parent folder of the plugins repository (`CellProfiler-plugins`), not the folder that contains plugins (`CellProfiler-plugins/active_plugins`). 

In order to get CellProfiler to open, remove `setup.py` from the `CellProfiler-plugins` folder. 
Open CellProfiler.
Change the CellProfiler Plugins path to the correct path and close CellProfiler. 
Return setup.py to the parent folder.  
OR  
Alternatively, you can edit the `PluginDirectory` line of your config to the correct path and then reload CellProfiler.
On Mac, you can find the config at `/Users/{username}/Library/Preferences/CellProfilerLocal.cfg`

For other troubleshooting information, please see the [Troubleshooting](https://plugins.cellprofiler.org/troubleshooting.html) page of our documentation.
