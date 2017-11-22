CellProfiler Microscope Image Focus Module Instructions
Note: the first time it's run, this module needs to download the model/weights, which can take a while.

OS X

From source (recommended)

Install CellProfiler from source
Using a terminal (found in Applications), install CellProfiler from source by running given commands in command line (instructions)
Get CellProfiler Plugin. In the terminal, run these commands:
```
MYDIR=/tmp/; cd MYDIR
git clone https://github.com/CellProfiler/CellProfiler-plugins.git  
cd CellProfiler-plugins/
git fetch origin pull/11/head:image-quality
git checkout image-quality
Install dependencies. In the terminal, run
pip install -r measureimagefocus_requirements.txt
```

To run CellProfiler, in the terminal run the following; note you may get import errors, but these can be safely ignored:
```
cellprofiler --plugins-directory
```

In CellProfiler,
Click "Images" and drag in images of interest [1]
Edit > Add Module > Measurement > MeasureImageFocus
Click on the module and in the module window choose Image > DNA (or name of image of interest)
To test module on a single image, click “Test Mode” and then click the step button or
 "Analyze Images" to run module on all images

From DMG

Not yet supported. Integration will come after the release of CellProfiler 3.0.

Windows

Not yet supported because the only Tensorflow package available on Windows uses Python 3.
[1]  Download the test images from https://storage.googleapis.com/microscope-image-quality/static/fiji_plugin_test_images.zip.  These images were excluded from the train dataset; the 6 focus examples were randomly selected and the other 2 examples show special cases.

