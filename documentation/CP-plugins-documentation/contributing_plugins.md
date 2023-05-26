# Contributing New Plugins

Within our CellProfiler wiki, you can find an [orientation to CellProfiler code](https://github.com/CellProfiler/CellProfiler/wiki/Orientation-to-CellProfiler-code).

In the CellProfiler repository, within [cellprofiler/modules/plugins](https://github.com/CellProfiler/CellProfiler/tree/master/cellprofiler/modules/plugins) you can find two different templates to use for creating your own plugin.
`imagetemplate.py` provides a template that takes one image as an input and produces a second image for downstream processing.
`measurementtemplate.py` provides a template that measures a property of an image both for the image as a whole and for every object in the image.

In you plugin, you must include:

In your plugin, we appreciate if you also include:
- display functionality
- extensive module documentation
- references and citation information in your module documentation

Please create a Pull Request to the CellProfiler-plugins repository to submit your plugin for inclusion in the repository.

In your PR, you must:
- add your plugin to the [supported_plugins](supported_plugins.md) documentation page

In your PR, we appreciate if you also include:
- unit tests for your plugin

## Having your plugin cited

While we cannot guarantee that users will cite your plugin, we have introduced a Citation generator into CellProfiler v? that scans all modules in a user's pipeline and generators a citation file for them that includes citation information for any modules (including plugins) that have specific citation information in them.