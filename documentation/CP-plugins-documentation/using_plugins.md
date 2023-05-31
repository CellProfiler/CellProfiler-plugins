# Using plugins

Once you have installed your plugins and their dependencies (see below), CellProfiler will automatically detect all plugins in the plugin folder that you have set.
The plugins will appear in the "Add Modules" panel like all standard modules and you can use the plugins as you would any other CellProfiler module.

Please note that, as CellProfiler-plugins are considered experimental, they may not be as well documented as standard modules and they may not have a window that shows on run. 
Please report any installation issues or bugs related to plugins in the [CellProfiler-plugins repository](https://github.com/CellProfiler/CellProfiler-plugins) and not in the main CellProfiler repository.

## Installation

If the plugin you would like to use does not have any additional dependencies outside of those required for running CellProfiler (this is most plugins), using plugins is very simple. 
See [Installing plugins without dependencies](#installing-plugins-without-dependencies).

If the plugin you would like to use has dependencies, you have two separate options for installation. 
The first option requires building CellProfiler from source, but plugin installation is simpler.
See [Installing plugins with dependencies, using CellProfiler from source](#installing-plugins-with-dependencies-using-cellprofiler-from-source).
The second option allows you to use pre-built CellProfiler, but plugin installation is more complex.
See [Installing plugins with dependencies, using pre-built CellProfiler](#installing-plugins-with-dependencies-using-pre-built-cellprofiler).

### Installing plugins without dependencies

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
- Close CellProfiler and re-open it

You are now ready to use any CellProfiler plugin that does not have additional dependencies.
This is most CellProfiler plugins.

### Installing plugins with dependencies, using CellProfiler from source

1. **Install CellProfiler.**  
Install CellProfiler from source (See instructions for: [Windows](https://github.com/CellProfiler/CellProfiler/wiki/Source-installation-%28Windows%29); [Mac Intel](https://github.com/CellProfiler/CellProfiler/wiki/Source-installation-%28OS-X-and-macOS%29); [Mac Apple Silicon](https://github.com/CellProfiler/CellProfiler/wiki/Installation-of-CellProfiler-4-from-source-on-MacOS-M1); [Linux](https://github.com/CellProfiler/CellProfiler/wiki/Source-installation-%28Linux%29))

2. **Clone the CellProfiler-plugins repository.** 
In your terminal, type
```bash
git clone https://github.com/CellProfiler/CellProfiler-plugins.git
```

3. **Set the plugins path in CellProfiler.**  
- Open CellProfiler. 
- Go to `CellProfiler` => `Preferences` and set the path in the `CellProfiler plugins directory` to the GitHub repository that you just cloned.
- Select `Save` at the bottom of the Preferences window
- Close CellProfiler

4. **Install the dependencies for your plugin.**
In your terminal, type the following, where FLAG is the flag specific to the module you would like to run, as noted in [Supported Plugins](supported_plugins.md).
```bash
cd CellProfiler-plugins
pip install -e .[FLAG]
```
e.g. To install Cellpose the pip install command would be `pip install -e .[cellpose]`

5. **Open and use CellProfiler.**  

Please note that plugins that have separate install flags may have conflicting dependencies so we recommend making a separate python environment in which to run separate installations.
(e.g. while having CellPose and StarDist in the same python environment is technically possible, it has been reported to be quite troublesome to install, so we recommend choosing either CellPose or StarDist.)

### Installing plugins with dependencies, using pre-built CellProfiler

1. **Install CellProfiler.**  
Download a binary (pre-built) version of CellProfiler from the [CellProfiler website](https://cellprofiler.org/releases).

2. **Clone the CellProfiler-plugins repository.** 
In your terminal, type
```bash
git clone https://github.com/CellProfiler/CellProfiler-plugins.git
```

3. **Set the plugins path in CellProfiler.**  
- Open CellProfiler. 
- Go to `CellProfiler` => `Preferences` and set the path in the `CellProfiler plugins directory` to the GitHub repository that you just cloned.
- Select `Save` at the bottom of the Preferences window
- Close CellProfiler

4. **Identify the Python dependencies of the plugins you want to use.**
You can find this information for most plugins by looking in `setup.py`.
```{admonition} e.g. using RunCellpose plugin
If you would like to install the RunCellpose plugin, in `setup.py` you can see that `cellpose_deps = ["cellpose>=1.0.2"]` so the only dependency is `cellpose`.
```

Alternatively, you can find this information directly in the plugin code itself by looking at what is imported at the beginning of the plugin.
Note that you will want to compare any imports to what is already required by CellProfiler with that caveat that dependencies often have dependencies.
```{admonition} e.g. using RunImageJScript plugin
If you would like to install the RunImageJScript plugin, you'll notice a number of imports in the beginning of the plugin code.
You can ignore all those from `cellprofiler_core` as they are required for CellProfiler installation.
You can ignore all those that are native to Python such as `sys`, `time`, and `threading`.
A comparison with CellProfiler dependencies will show you that `skimage` is already installed (you can see this in CellProfiler's [environment.yml](https://github.com/CellProfiler/CellProfiler/blob/master/environment.yml) which lists `scikit-image` as a `cellprofiler-core` dependency or in CellProfiler's [setup.py](https://github.com/CellProfiler/CellProfiler/blob/master/setup.py) which lists `scikit-image` as an installation requirement).
What remains is `pyimagej`
```

5. **Create a conda environment and install requirements in it**
Create a conda (or other virtual) environment with a Python version matching that of CellProfiler.
CellProfiler 4 uses Python 3.8 (which you can see in CellProfiler's [setup.py](https://github.com/CellProfiler/CellProfiler/blob/master/setup.py)).
Activate the environment and install the plugin requirement/s into it.

In your terminal, type
```
# Create a conda environment
conda create --name ENV_NAME python=3.8
# Activate the conda environment
conda activate ENV_NAME
# Install the plugin requirement/s
pip install REQUIREMENT
```
```{admonition} e.g. using RunImageJScript plugin
conda create --name cp-ij python=3.8
conda activate cp-ij
pip install pyimagej
```

6. **Copy plugin requirements into CellProfiler installation**
Find the folder that you installed into in the previous step (where to find these libraries in your local environment) by entering `pip show REQUIREMENT` into your terminal e.g. `pip show pyimagej`.
In the information it returns, under `Location` you will find a path that will look something like `/Users/eweisbar/mambaforge/envs/cp-ij/lib/python3.8/site-packages`.

Find the folder in which you have installed CellProfiler.
On Windows this is likely to be `C:\Program Files\CellProfiler` and on Mac it is likely to be `/Applications/CellProfiler.app/Contents/MacOS/`.
In your terminal, if you `ls` (for Mac) or `dir` (for Windows) that folder (e.g. `ls /Applications/CellProfiler.app/Contents/MacOS/`), you should see a list of all the dependencies that were packaged with CellProfiler. 

Copy the folders and their corresponding `.dist-info` folders (e.g. `pytz` and `pytz-2023.3.dist-info`) for any dependencies that were installed with the installation of `pyimagej` that are not already in the CellProfiler folder.

```{admonition} e.g. using RunImageJScript plugin
These are all the folders you need to copy over:
`pytz`
`pytz-2023.3.dist-info`
`xarray`
`xarray-2023.1.0.dist-info`
`imglyb`
`imglyb-2.1.0.dist-info`
`jgo`
`jgo-1.0.5.dist-info`
`jpype`
`_jpype.cpython-38-darwin.so`
`imagej`
`pyimagej-1.4.1.dist-info`
```

7. **Open and use CellProfiler.**
When you try to run your plugin in your pipeline, if you have missed copying over any specific requirements, it will give you an error message that will tell you what dependency is missing.