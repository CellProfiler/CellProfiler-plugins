# Using plugins

Once you have installed your plugins and their dependencies (see below), CellProfiler will automatically detect all plugins in the plugin folder that you have set.
The plugins will appear in the "Add Modules" panel like all standard modules and you can use the plugins as you would any other CellProfiler module.

Please note that, as CellProfiler-plugins are considered experimental, they may not be as well documented as standard modules and they may not have a window that shows on run. 
Please report any installation issues or bugs related to plugins in the [CellProfiler-plugins repository](https://github.com/CellProfiler/CellProfiler-plugins) and not in the main CellProfiler repository.

## Installation

### Installing plugins without dependencies

If your plugin doesn't require additional dependencies, all you need to do is 

1. **Install CellProfiler.**  
Download a binary (pre-built) version of CellProfiler from the [CellProfiler website](https://cellprofiler.org/releases).

Or, you can install CellProfiler from source (See instructions for: [Windows](https://github.com/CellProfiler/CellProfiler/wiki/Source-installation-%28Windows%29); [Mac Intel](https://github.com/CellProfiler/CellProfiler/wiki/Source-installation-%28OS-X-and-macOS%29); [Mac Apple Silicon](https://github.com/CellProfiler/CellProfiler/wiki/Installation-of-CellProfiler-4-from-source-on-MacOS-M1); [Linux](https://github.com/CellProfiler/CellProfiler/wiki/Source-installation-%28Linux%29))

2. **Clone the CellProfiler-plugins repository.** 
This will download all of the plugins in the CellProfiler-plugins repository.

In your terminal, type
```bash
git clone https://github.com/CellProfiler/CellProfiler-plugins.git
```

Alternatively, if you have code for plugins that are not in the CellProfiler-plugins repository, you can place them in any folder that you'll be able to find again.

3. **Set the plugins path in CellProfiler.**  
- Open CellProfiler. 
- Go to `CellProfiler` => `Preferences` and set the path in the `CellProfiler plugins directory` to the GitHub repository that you just cloned (or, if you didn't clone the whole repository, whatever location you have saved your plugins into).
- Select `Save` at the bottom of the Preferences window
- Close CellProfiler and re-open it.

You are now ready to use any CellProfiler plugin that does not have additional dependencies.
This is most CellProfiler plugins.

### Installing plugins with dependencies

1. **Install CellProfiler.**  
Install CellProfiler from source (See instructions for: [Windows](https://github.com/CellProfiler/CellProfiler/wiki/Source-installation-%28Windows%29); [Mac Intel](https://github.com/CellProfiler/CellProfiler/wiki/Source-installation-%28OS-X-and-macOS%29); [Mac Apple Silicon](https://github.com/CellProfiler/CellProfiler/wiki/Installation-of-CellProfiler-4-from-source-on-MacOS-M1); [Linux](https://github.com/CellProfiler/CellProfiler/wiki/Source-installation-%28Linux%29))

2. **Clone the CellProfiler-plugins repository.** 
In your terminal, type
```bash
git clone https://github.com/CellProfiler/CellProfiler-plugins.git
```

3. **Set the plugins path in CellProfiler.**  
- Open CellProfiler. 
- Go to `CellProfiler` => `Preferences` and set the path in the `CellProfiler plugins directory` to the GitHub repository that you just cloned (or, if you didn't clone the whole repository, whatever location you have saved your plugins into).
- Select `Save` at the bottom of the Preferences window
- Close CellProfiler and re-open it.

4. **Install the dependencies for your plugin.**
In your terminal, type the following, where FLAG is the flag specific to the module you would like to run, as noted in [Supported Plugins](supported_plugins.md).
```bash
cd CellProfiler-plugins
pip install -e .[FLAG]
```

Please note that plugins that have separate install flags may have conflicting dependencies so we recommend making a separate python environment in which to run separate installations.
(e.g. while having CellPose and StarDist in the same python environment is technically possible, it has been reported to be quite troublesome to install, so we recommend choosing either CellPose or StarDist.)