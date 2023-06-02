# RunDeepProfiler

## How to use RunDeepProfiler

### Windows

1. Create an environment to run CellProfiler and DeepProfiler:

```
conda create --name cp-dp python=3.8
```

Activate the environment:

```
conda activate cp-dp
```

2. Follow the [instructions](using_plugins.md) to install CellProfiler from source;

3. Clone DeepProfiler repository:

```
git clone https://github.com/broadinstitute/DeepProfiler.git
```

4. Install DeepProfiler

```
cd DeepProfiler /
pip install -e .
```

5. Install dependencies by running:

```
pip install numpy==1.23.0
pip install inflect==6.0.0
```

6. Run CellProfiler

Call `cellprofiler` in the command line and see if you can find RunDeepProfiler by adding the module.

7. Select the cellprofiler-plugins/active_plugins folder in Preferences > Save

8. Use the folder with images and files available on CellProfiler-plugins > test > test_deepprofiler [link here]() as an example to run the test pipeline test_deepprofiler.cppipe

9. Don't forget to select the config, model, and DeepProfiler directories to your local paths.



## Using GPU

If you want to use a GPU to run the model (this is recommended for speed), you'll need a compatible version of Tensorflow and a supported GPU. 
General instructions are available at this [link](https://www.tensorflow.org/guide/gpu).

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