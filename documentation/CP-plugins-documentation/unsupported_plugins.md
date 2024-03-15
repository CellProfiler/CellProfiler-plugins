# Currently Unsupported Plugins

Unsupported plugins are primarily unsupported for either of two reasons:
- They were made for a previous major version of CellProfiler and have not been updated to be compatible with the current version
- Their functions have been integrated into the current version of CellProfiler and therefore a plugin is no longer necessary

We welcome requests for updating particular unsupported plugins, but please note that we have limited bandwidth for working on plugins and may be unable to complete the update.
Additionally, we cannot commit to maintaining any given plugin, CellProfiler team- or community-contributed.
We welcome community contributed plugin updates.

## Where are unsupported plugins?

Unsupported plugins can be found in the `unmaintained_plugins` folder in the CellProfiler-plugins repository.
Those plugins in the `CellProfiler2`, `CellProfiler3`, and `CellProfiler4` folders were, at one point, supported for those versions of CellProfiler. 
Those plugins in the `CellProfiler4_autoconverted` folder were automatically converted from Python2 to Python3 (to support the transition from Python2 in CellProfiler3 to Python3 in CellProfiler4) but were never fully supported and may or may not run.

## What plugins are unsupported?

We cannot provide comprehensive information about why we are not supporting a given plugin.
Information about select plugins is as follows:

**ClassifyPixelsUNET**: ClassifyPixelsUNET is a pixel classifier for background/object edge/object body. As far as we are aware, other deep learning  based plugins that we do currently support (such as RunCellpose) work better.
**DeclumpObjects**: DeclumpObjects will split objects based on a seeded watershed method. Functionality from this module was [added into CellProfiler](https://github.com/CellProfiler/CellProfiler/pull/4397) in the Watershed module as of CellProfiler 4.2.0.
**Predict**: Predict module is not supported anymore and one can use **Runilastik** module to run ilastik pixel classifier in Cellprofiler. 
