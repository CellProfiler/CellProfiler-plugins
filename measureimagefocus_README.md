CellProfiler Microscope Image Focus Module Instructions

The implementation of this plugin is described in and the URL for this page ("https://github.com/CellProfiler/CellProfiler-plugins/blob/master/measureimagefocus_README.md") is linked from this paper: Yang, S. J.; Berndl, M. & Ando, D. M. et al. (2017), "Assessing microscope image focus quality with deep learning", (accepted).

Note: the first time it's run, this module needs to download the model/weights, which can take a while.

OS X

From source (recommended)

1. Install CellProfiler from source
2. Get CellProfiler Plugin. In the terminal, run these commands:
```
MYDIR=/tmp/; cd MYDIR
git clone https://github.com/CellProfiler/CellProfiler-plugins.git  
cd CellProfiler-plugins/
Install dependencies. In the terminal, run
pip install -r requirements.txt
```

3. To run CellProfiler, in the terminal run the following; note you may get import errors, but these can be safely ignored:
```
cellprofiler --plugins-directory MYDIR/CellProfiler-plugins
```

4. In CellProfiler,
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

