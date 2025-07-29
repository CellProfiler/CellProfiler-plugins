# RunCellpose

You can run RunCellpose using Cellpose in a Docker that the module will automatically download for you so you do not have to perform any installation yourself.
See [Using plugins - Using Docker](using_plugins.md/#using-docker-to-bypass-installation-requirements) for more information on using Docker with CellProfiler.

You can also this module using Cellpose installed to the same Python environment as CellProfiler.
See [Using plugins - Installing dependencies](using_plugins.md/#installing-plugins-with-dependencies-using-cellprofiler-from-source) for more information on installing dependencies for CellProfiler plugins.

## Installing Cellpose in the same Python environment as CellProfiler

We provide some information below about installations that have worked for us.
If you are having challenges with installing Cellpose in your CellProfiler environment, please reach out on the [forum](https://forum.image.sc/).

### Omnipose (Cellpose 1)

In an environment that has Cellprofiler installed, run the following commands to install Omnipose and Cellpose 1:

```bash
pip install omnipose
pip install cellpose==1.0.2
```

### Cellpose 2

In an environment that has Cellprofiler installed, run the following commands to install Cellpose 2:

```bash
pip install cellpose==2.3.2
```

If you have an older version of Cellpose, run the following command to reinstall Cellpose 2:

```bash
python -m pip install --force-reinstall -v cellpose==2.3.2
```

### Cellpose 3

On Mac M1/M2, to create a new environment with CellProfiler and Cellpose 4, run the following commands:

```bash
export LDFLAGS="-L/opt/homebrew/opt/mysql@8.0/lib"    
export CPPFLAGS="-I/opt/homebrew/opt/mysql@8.0/include"
export PKG_CONFIG_PATH="/opt/homebrew/opt/mysql@8.0/lib/pkgconfig"
conda create -y --force -n cellpose3_cellprofiler python=3.9 h5py=3.6.0 python.app scikit-learn==0.24.2 scikit-image==0.18.3 openjdk 
conda activate cellpose3_cellprofiler
pip install cellpose==3.1.1.2
pip install mysqlclient==1.4.6 cellprofiler
```

### Cellpose-SAM (Cellpose 4)

On Mac M1/M2, to create a new environment with CellProfiler and Cellpose 4, run the following commands:

```bash
export LDFLAGS="-L/opt/homebrew/opt/mysql@8.0/lib"    
export CPPFLAGS="-I/opt/homebrew/opt/mysql@8.0/include"
export PKG_CONFIG_PATH="/opt/homebrew/opt/mysql@8.0/lib/pkgconfig"
conda create -y --force -n cellposeSAM_cellprofiler python=3.9 h5py=3.6.0 python.app scikit-learn==0.24.2 scikit-image==0.18.3 openjdk 
conda activate cellposeSAM_cellprofiler
pip install cellpose==4.0.6
pip install mysqlclient==1.4.6 cellprofiler
```

## Using RunCellpose with a GPU

If you want to use a GPU to run the model (this is recommended for speed), you'll need a compatible version of PyTorch and a supported GPU.
General instructions are available at this [link](https://pytorch.org/get-started/locally/).

1. Your GPU should be visible in Device Manager under Display Adaptors. 
If your GPU isn't there, you likely need to install drivers.
[Here](https://www.nvidia.com/Download/Find.aspx) is where you can find NVIDIA GPU drivers if you need to install them.


2. To test whether the GPU is configured correctly:
  * Run `python` on the command line (i.e., in Command Prompt or Terminal) to start an interactive session
  * Then run the following
  ```
  import torch
  torch.cuda.is_available()
  ```
  * If this returns `True`, you're all set
  * If this returns `False`, you likely need to install/reinstall torch. See [here](https://pytorch.org/get-started/locally/) for your exact command.
  * Exit the session with `exit()` then install torch if necessary
  ```
  pip3 install torch torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/cu113
  ```
  If you have a previous version of torch installed, make sure to run `pip uninstall torch` first.


**NOTE**: You might get a warning like this:
```
W tensorflow/stream_executor/platform/default/dso_loader.cc:64] Could not load dynamic library 'cudart64_110.dll'; dlerror: cudart64_110.dll not found
2022-05-26 20:24:21.906286: I tensorflow/stream_executor/cuda/cudart_stub.cc:29] Ignore above cudart dlerror if you do not have a GPU set up on your machine.
```
If you don't have a GPU, this is not a problem.
If you do, your configuration is incorrect and you need to try reinstalling drivers and the correct version of CUDA for your system.
