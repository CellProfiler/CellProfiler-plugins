# Supported Plugins

Below is a brief overview of our currently supported plugins.
For details about using any particular plugin, please read the module documentation inside the plugin in CellProfiler.

Most plugins will run without any special installation of either CellProfiler or the plugins.
See [using plugins](using_plugins.md) for how to set up CellProfiler for plugin use as well as for installation information for those plugins that do require installation of dependencies.

Most plugin documentation can be found within the plugin itself and can be accessed through CellProfiler help.
Those plugins that do have extra documentation contain links below.

| Plugin | Description | Requires installation of dependencies? | Install flag | Docker version currently available? |
|--------|-------------|----------------------------------------|--------------|-------------------------------------|
| AddNoise      | AddNoise adds Gaussian, Poisson, or Salt and Pepper noise to images. Of particular use for data augmentation in deep learning. | No | | N/A |
| CalculateMoments      | CalculateMoments extracts moments statistics from a given distribution of pixel values. | No | | N/A |
| CallBarcodes          | CallBarcodes is used for assigning a barcode to an object based on the channel with the strongest intensity for a given number of cycles. It is used for optical sequencing by synthesis (SBS). | No | | N/A |
| CompensateColors      | CompensateColors determines how much signal in any given channel is because of bleed-through from another channel and removes the bleed-through. It can be performed across an image or masked to objects and provides a number of preprocessing and rescaling options to allow for troubleshooting if input image intensities are not well matched. | No | | N/A |
| DistanceTransform     | DistanceTransform computes the distance transform of a binary image. The distance of each foreground pixel is computed to the nearest background pixel and the resulting image is then scaled so that the largest distance is 1. | No | | N/A |
| EnforceObjectsOneToOne| EnforceObjectsOneToOne generates Primary and Secondary object relationships for any pair of objects in a similar manner to the relationships established by IdentifyPrimaryObjects and IdentifySecondaryObjects. It is particularly useful for relating objects identified using Deep Learning. | No | | N/A |
| EnhancedMeasureTexture| EnhancedMeasureTexture measures the degree and nature of textures within an image or objects in a more comprehensive/tuneable manner than the MeasureTexture module native to CellProfiler. | No | | N/A |
| FilterObjects_StringMatch| FilterObjects_StringMatch allows filtering of objects using exact or partial string matching in a manner similar to FilterObjects. | No | | N/A |
| HistogramEqualization | HistogramEqualization increases the global contrast of a low-contrast image or volume. Histogram equalization redistributes intensities to utilize the full range of intensities, such that the most common frequencies are more distinct. This module can perform either global or local histogram equalization. | No | | N/A |
| HistogramMatching     | HistogramMatching manipulates the pixel intensity values an input image and matches them to the histogram of a reference image. It can be used as a way to normalize intensities across different 2D or 3D images or different frames of the same 3D image. It allows you to choose which frame to use as the reference. | No | | N/A |
| PixelShuffle          | PixelShuffle takes the intensity of each pixel in an image and randomly shuffles its position. | No | | N/A |
| [RunCellpose](RunCellPose.md) | RunCellpose allows you to run Cellpose within CellProfiler. Cellpose is a generalist machine-learning algorithm for cellular segmentation and is a great starting point for segmenting non-round cells. You can use pre-trained Cellpose models or your custom model with this plugin. You can use a GPU with this module to dramatically increase your speed/efficiency. | Yes | `cellpose` | Yes |
| Runilastik            | Runilasitk allows to run ilastik within CellProfiler. You can use pre-trained ilastik projects/models to predict the probability of your input images. The plugin supports two types of ilastik projects: Pixel Classification and Autocontext (2-stage).| Yes |  | Yes |
| RunImageJScript       | RunImageJScript allows you to run any supported ImageJ script directly within CellProfiler. It is significantly more performant than RunImageJMacro, and is also less likely to leave behind temporary files. | Yes | `imagejscript` , though note that conda installation may be preferred, see [this link](https://py.imagej.net/en/latest/Install.html#installing-via-pip) for more information | No |
| RunOmnipose           | RunOmnipose allows you to run Omnipose within CellProfiler. Omnipose is a general image segmentation tool that builds on Cellpose. | Yes | `omnipose` | No |
| RunStarDist           | RunStarDist allows you to run StarDist within CellProfiler. StarDist is a machine-learning algorithm for object detection with star-convex shapes making it best suited for nuclei or round-ish cells. You can use pre-trained StarDist models or your custom model with this plugin. You can use a GPU with this module to dramatically increase your speed/efficiency. RunStarDist is generally faster than RunCellpose. | Yes | `stardist` | No |
| VarianceTransform     | This module allows you to calculate the variance of an image, using a determined window size. It also has the option to find the optimal window size from a predetermined range to obtain the maximum variance of an image. | No | | N/A |
