CellProfiler-plugins
====================
[![Build Status](https://travis-ci.org/CellProfiler/CellProfiler-plugins.svg?branch=master)](https://travis-ci.org/CellProfiler/CellProfiler-plugins)

A home for community-contributed and experimental CellProfiler modules. 

## Beginner-level instructions
Please see help here: https://github.com/CellProfiler/CellProfiler/blob/master/cellprofiler/data/help/other_plugins.rst

## Use
1. Clone this repository:
    ```
    cd PLUGIN_DIRECTORY
    git clone https://github.com/CellProfiler/CellProfiler-plugins.git
    ```
    
    Alternatively download zip and manually extract to PLUGIN_DIRECTORY.

1. Install required dependencies:
	```
	cd CellProfiler-plugins
	pip install -r requirements.txt
	```

    To install CellProfiler-plugins on a windows machine with support for the deep learning module ClassifyPixels-UNet make sure you have Visual Studio 2017 installed then use
    ```
    cd CellProfiler-plugins
    pip install -r requirements-windows.txt
    ```

1. Configure CellProfiler plugins directory in the GUI via `Preferences > CellProfiler plugins directory` (you will need to restart CellProfiler for the change to take effect). When running CellProfiler via the command line, use the `--plugins-directory` flag to specify the plugins directory, for example:
    ```
    cellprofiler --run --run-headless --project PROJECT_FILE --plugins-directory PLUGIN_DIRECTORY/CellProfiler-plugins
    ```

## ImageJ requirements

 If using the `RunImageJScript` module, please note:
 * You will also need to [install Maven](https://github.com/imagej/pyimagej/blob/master/doc/Install.md#installing-via-pip)
 * CellProfiler will need to be [built from source](https://github.com/CellProfiler/CellProfiler/blob/master/cellprofiler/data/help/other_plugins.rst) due to the requirement of additional libraries
