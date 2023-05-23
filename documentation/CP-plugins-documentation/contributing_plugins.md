## Contributing New Plugins

Refer to CellProfiler repository and within cellprofiler/modules/plugins you can find two different templates to use for creating your own plugin.
`imagetemplate.py` provides a template that takes one image as an input and produces a second image for downstream processing.
`measurementtemplate.py` provides a template that measures a property of an image both for the image as a whole and for every object in the image.

In you plugin, you must include:

In your plugin, we appreciate if you also include:
- display functionality


In your PR, you must include:
- add your plugin to the [supported_plugins](supported_plugins.md) documentation page

In your PR, we appreciate if you also include:
- unit tests for your plugin