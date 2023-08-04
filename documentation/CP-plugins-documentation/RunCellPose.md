# RunCellpose

RunCellpose is one of the modules that has additional dependencies that are not packaged with the built CellProfiler. 
Therefore, you must additionally download RunCellpose's dependencies.
See [Using Plugins](using_plugins.md) for more information.

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
If you don't have a GPU, this is not a problem. If you do, your configuration is incorrect and you need to try reinstalling drivers and the correct version of CUDA for your system.