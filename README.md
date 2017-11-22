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

1. Configure CellProfiler plugins directory in the GUI via `Preferences > CellProfiler plugins directory` (you will need to restart CellProfiler for the change to take effect). When running CellProfiler via the command line, use the `--plugins-directory` flag to specify the plugins directory, for example:
    ```
    cellprofiler --run --run-headless --project PROJECT_FILE --plugins-directory PLUGIN_DIRECTORY
    ```
