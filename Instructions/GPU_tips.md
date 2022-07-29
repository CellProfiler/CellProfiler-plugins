# Tips on setting up your GPU

Updated June 28, 2022

## Setup your GPU (if you have one)

If you want to use a GPU to run the model (this is recommended for speed), you'll need a compatible version of PyTorch and a supported GPU. General instructions are available at this [link](https://pytorch.org/get-started/locally/).

1. Your GPU should be visible in Device Manager under Display Adaptors. If your GPU isn't there, you likely need to install drivers.
    * [Here](https://www.nvidia.com/Download/Find.aspx) is where you can find NVIDIA GPU drivers if you need to install them.


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
