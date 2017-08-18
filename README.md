CellProfiler-plugins
====================

A home for community-contributed and experimental CellProfiler modules.

## Use
1. Clone this repository:
    ```
    cd PLUGIN_DIRECTORY
    git clone https://github.com/CellProfiler/CellProfiler-plugins.git
    ```
    
    Alternatively download zip and manually extract to PLUGIN_DIRECTORY.

1. Configure CellProfiler plugins directory in the GUI via `Preferences > CellProfiler plugins directory` (you will need to restart CellProfiler for the change to take effect). When running CellProfiler via the command line, use the `--plugins-directory` flag to specify the plugins directory, for example:
    ```
    cellprofiler --run --run-headless --project PROJECT_FILE --plugins-directory PLUGIN_DIRECTORY
    ```
