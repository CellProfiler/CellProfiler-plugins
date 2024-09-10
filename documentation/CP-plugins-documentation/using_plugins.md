# Using plugins

Once you have installed your plugins and their dependencies (see below), CellProfiler will automatically detect all useable plugins in the plugin folder that you have set.
The plugins will appear in the "Add Modules" panel like all standard modules and you can use the plugins as you would any other CellProfiler module.
Typically, if a plugin's dependencies are not installed, it will not be visible in the "Add Modules" panel.
If you cannot find any plugins in the "Add Modules" panel then you have not properly set the plugins path (see below).
If you can find some but not all plugins in the "Add Modules" panel then the not-visible plugins have unmet dependencies.

Please note that, as CellProfiler-plugins are considered experimental, they may not be as well documented as standard modules and they may not have a window that shows on run. 
Please report any installation issues or bugs related to plugins in the [CellProfiler-plugins repository](https://github.com/CellProfiler/CellProfiler-plugins) and not in the main CellProfiler repository.

## Installation

If the plugin you would like to use does not have any additional dependencies outside of those required for running CellProfiler (this is most plugins), using plugins is very simple. 
See [Installing plugins without dependencies](#installing-plugins-without-dependencies).

If the plugin you would like to use has dependencies, you have three separate options for installation. 
- The first option requires building CellProfiler from source, but plugin installation is simpler.
See [Installing plugins with dependencies, using CellProfiler from source](#installing-plugins-with-dependencies-using-cellprofiler-from-source).
- The second option allows you to use pre-built CellProfiler, but plugin installation is more complex.
See [Installing plugins with dependencies, using pre-built CellProfiler](#installing-plugins-with-dependencies-using-pre-built-cellprofiler).
- The third option uses Docker to bypass installation requirements. 
It is the simplest option that only requires download of Docker Desktop; the module that has dependencies will automatically download a Docker that has all of the dependencies upon run and access that Docker while running the plugin.
It is currently supported for the RunCellpose and Runilastik plugins. Please have a look at this [table](https://github.com/CellProfiler/CellProfiler-plugins/blob/master/documentation/CP-plugins-documentation/supported_plugins.md) to know about the availability of docker versions for plugins.  
See [Using Docker to Bypass Installation Requirements](#using-docker-to-bypass-installation-requirements).

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
    - Go to `CellProfiler` => `Preferences` and set the path in the `CellProfiler plugins directory` to the `active_plugins` folder in the GitHub repository that you just cloned (or, if you didn't clone the whole repository, whatever location you have saved your plugins into).
    - Select `Save` at the bottom of the Preferences window
    - Close CellProfiler and re-open it
    
    You are now ready to use any CellProfiler plugin that does not have additional dependencies.
    This is most CellProfiler plugins.

### Installing plugins with dependencies, using CellProfiler from source

1. **Install CellProfiler.**

    Install CellProfiler from source (See instructions for: [Windows](https://github.com/CellProfiler/CellProfiler/wiki/Source-installation-%28Windows%29); [Mac Intel](https://github.com/CellProfiler/CellProfiler/wiki/Source-installation-%28OS-X-and-macOS%29); [Mac Apple Silicon](https://github.com/CellProfiler/CellProfiler/wiki/Installation-of-CellProfiler-4-from-source-on-MacOS-M1); [Linux](https://github.com/CellProfiler/CellProfiler/wiki/Source-installation-%28Linux%29))

2. **Clone the CellProfiler-plugins repository.**

    In your terminal, type:

    ```bash
    git clone https://github.com/CellProfiler/CellProfiler-plugins.git
    ```

3. **Set the plugins path in CellProfiler.**

    - Open CellProfiler. 
    - Go to `CellProfiler` => `Preferences` and set the path in the `CellProfiler plugins directory` to the `active_plugins` folder in the GitHub repository that you just cloned.
    - Select `Save` at the bottom of the Preferences window
    - Close CellProfiler

4. **Install the dependencies for your plugin.**

    In your terminal, type the following, where FLAG is the flag specific to the module you would like to run, as noted in [Supported Plugins](supported_plugins.md):

    ```bash
    cd CellProfiler-plugins
    pip install -e .[FLAG]
    ```

    e.g. To install Cellpose the pip install command would be `pip install -e .[cellpose]`
    
    If using Mac and getting an error saying `zsh: no matches found: .[somepackage]`, put the dot and square brackets in single quotes, ie `pip install -e '.[cellpose]'`

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
    - Go to `CellProfiler` => `Preferences` and set the path in the `CellProfiler plugins directory` to the `active_plugins` folder in the GitHub repository that you just cloned.
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

5. **Initialize the proper version of python**

    For the subsequent steps, make sure to use the same version of python that CellProfiler uses. For instance, CellProfiler 4 uses python 3.8, (which you can see in CellProfiler's [setup.py](https://github.com/CellProfiler/CellProfiler/blob/4.2.x/setup.py)). You can check what version of python you're using in the terminal:

    ```bash
    python --version
    ```

    If necessary, you can create a conda environment with a specific version of python.

    ```bash
    conda create --name py38 python=3.8
    conda activate py38
    ```

    You may replace the value after `--name` with whatever name you'd like to give to the environment.
    If you don't have `conda`/`miniconda`/`mamba` or similar, you can either [manually install python directly](https://www.python.org/downloads/), or use a tool like `pyenv` to manage different versions of python:
    - [pyenv Mac](https://github.com/pyenv/pyenv)
    - [pyenv Windows](https://github.com/pyenv-win/pyenv-win)

    ```{note}
    If you have multiple versions of python (e.g. you have python 3.8 and python 3.9 both installed with homebrew on Mac), it is sometimes the case that you may need to specify an exact `pip` version in the below steps, e.g. `pip3.8` instead of just `pip`. You can always double check you're using the correct pip with `pip --version`.
    ```

6. **Install or copy requirements into CellProfiler installation.**

    Find the folder in which you have installed CellProfiler. On Windows, this is likely to be `C:\Program Files\CellProfiler`, and on Mac, it is likely to be `/Applications/CellProfiler.app/Contents/MacOS/`, but otherwise will be `/path/to/CellProfiler.app/Contents/MacOS/`.
    If you're curious, you can run `ls` (on Mac) or `dir` (Windows) on this directory, and you will see all of the dependencies that were packaged with CellProfiler.

    In your terminal run a pip installation, replacing `</path/to/CellProfiler>` with the path you found above. If you're on Windows, depending on where CellProfiler is installed, you may need to do this in a terminal running with admin privileges, which you can do by right-clicking on `cmd.exe` (or `powershell`) and clicking "Run as Administrator".

    ```bash
    pip install --target=</path/to/CellProfiler> REQUIRMENTS
    ```

    ```{admonition} e.g. using RunImageJ script
    conda create –name cp-ij python=3.8
    
    conda activate cp-ij
    
    pip install --target=/Applications/CellProfiler.app/Contents/MacOS/ pyimagej
    ```

    ```{note}
    Do not run the `pip install` from *within* the CellProfiler directory. If you run `pip` with your terminal's current working directory inside the CellProfiler directory, you will confuse `pip`, since there is a version of python bundled with CellProfiler and your `PATH` and/or `PYTHONPATH` may include your current working directory.
    ```

    ```{note}
    Do not use the `-U` or `--upgrade` flag as that will overwrite existing CellProfiler dependencies with potentially incompatible ones.
    ```

    Alternatively, you may install the dependencies as usual, and manually copy over only specific requirements into the CellProfiler directory. To do this with `conda` or similar, you may activate that environment and simply run pip without the `--target` flag:

    ```bash
    pip install REQUIRMENTS
    ```

    ```{admonition} e.g. using RunImageJ script
    conda create –name cp-ij python=3.8

    conda activate cp-ij

    pip install pyimagej
    ```

    Then you may find the default folder that `pip` installs packages into by entering `pip show REQUIREMENT` into your terminal e.g. `pip show pyimagej`.
    In the information it returns, under `Location` you will find a path that will look something like (Mac) `/Users/username/mambaforge/envs/cp-ij/lib/python3.8/site-packages` or (Windows) `c:\users\username\miniforge3\envs\cp\lib\site-packages`.

    Finally you may manually copy the folders and their corresponding `.dist-info` folders (e.g. `pytz` and `pytz-2023.3.dist-info`) for any dependencies that were installed with the installation of e.g. `pyimagej` that are not already in the CellProfiler folder.

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

    When you try to run your plugin in your pipeline, if you have missed copying over any specific requirements, it will give you an error message that will tell you what dependency is missing in the terminal window that opens with CellProfiler on Windows machines.

    This information is not available in Mac machines when you launch the application directly (by double clicking `CellProfiler.app`). However you may instead open the application with your terminal: `/path/to/CellProfiler.app/Contents/MacOS/cp`.

### Using Docker to bypass installation requirements

1. **Download Docker**

    Download Docker Desktop from [Docker.com](https://www.docker.com/products/docker-desktop/).

2. **Run Docker Desktop**
Open Docker Desktop.

Docker Desktop will need to be open every time you use a plugin with Docker. Please have a look at this [table](https://github.com/CellProfiler/CellProfiler-plugins/blob/master/documentation/CP-plugins-documentation/supported_plugins.md) to know if a docker version is available for a plugin. 

3. **Select "Run with Docker"**

    In your plugin, select `Docker` for "Run module in docker or local python environment" setting.

    On the first run of the plugin, the Docker container will be downloaded, however, this slow downloading process will only have to happen once.

