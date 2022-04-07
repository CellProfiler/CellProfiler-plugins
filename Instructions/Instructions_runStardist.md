# Instructions for installing runStardist

Updated April 7, 2022

## Setup your GPU (if you have one)

If you want to use a GPU to run the model (this is recommended for speed), you'll need a compatible version of PyTorch and a supported GPU. Instructions are available at this link: (https://pytorch.org/get-started/locally/)

1. Your GPU should be visible in Device Manager under Display Adaptors. If your GPU isn't there, you likely need to install drivers.
 - Here (https://www.nvidia.com/Download/Find.aspx) is where you can find NVIDIA GPU drivers if you need to install them.


2. To test whether the GPU is configured correctly:
  1. Run `python` on the command line (i.e., in Command Prompt or Terminal) to start an interactive session
  2. Then run the following
  ```
  import torch
  torch.cuda.is_available()
  ```
  3. If this returns `True`, you're all set
  4. If this returns `False`, you likely need to install/reinstall torch. See https://pytorch.org/get-started/locally/ for your exact command.
  ```
  pip3 install torch torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/cu113
  ```
  If you have a previous version of torch installed, make sure to run `pip uninstall torch` first.


## Clone the CellProfiler plugins repo

1. Clone the CellProfiler-plugins runCellpose (PLUGIN_DIRECTORY is the folder to which you'd like to download the CellProfiler-plugins folder)
```
cd PLUGIN_DIRECTORY
git clone https://github.com/CellProfiler/CellProfiler-plugins.git
```

## Install required dependencies

1. Because of conflicting dependencies, first run the following:
```
pip install --no-deps csbdeep
```
Then install stardist and tensorflow:
```
pip install tensorflow stardist
```

2. On Windows, install Visual Studio 2017 (https://support.microsoft.com/help/2977003/the-latest-supported-visual-c-downloads)

## Point CellProfiler to the CellProfiler-plugins folder

1. Open CellProfiler (enter `cellprofiler` on command line or if on Mac and you get an error about the program needing access to the screen, enter `pythonw -m cellprofiler`) and go to **File** > **Preferences...** > Change **CellProfiler plugins directory** to the location of your CellProfiler-plugins/ folder

2. Close and reopen CellProfiler

3. If using the pre-trained models, StarDist will download each when first used. The models will automatically run on a GPU if compatible hardware is available. A guide to setting up Tensorflow GPU integration can be found at this link: https://www.tensorflow.org/install/gpu


### Note, if you have a GPU and use runCellpose with RunStardist, you may encounter difficulties with GPU memory if your pipeline has a RunStardist module followed by a runCellpose module.
