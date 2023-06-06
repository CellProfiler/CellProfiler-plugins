# RunDeepProfiler

## How to use RunDeepProfiler

### Windows

1. Follow the instructions to install CellProfiler from source: [Installing plugins with dependencies, using CellProfiler from source](using_plugins.md);

2. Clone DeepProfiler repository:

```
git clone https://github.com/broadinstitute/DeepProfiler.git
```

4. Install DeepProfiler

```
cd DeepProfiler /
pip install -e .
```

5. Install dependencies by running:

```bash
cd CellProfiler-plugins
pip install -e .[deepprofiler]
```

## Run Example

1. Use the folder with images and files available on CellProfiler-plugins > test > test_deepprofiler [link here](https://github.com/CellProfiler/CellProfiler-plugins/pull/182/commits/62874b4a28a370cea069662d3804a68b651130ec) as an example to run the test pipeline test_deepprofiler.cppipe

2. Don't forget to select the config, model, and DeepProfiler directories to your local paths.


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
  import tensorflow as tf
  tf.test.is_gpu_available(
    cuda_only=False, min_cuda_compute_capability=None
)
  ```
  * If this returns `True`, you're all set
  * If this returns `False`, you likely need to install/reinstall torch. See [here](https://www.tensorflow.org/guide/gpu) for your exact command.
  * Exit the session with `exit()` then install tensorflow if necessary.


**NOTE**: You might get a warning like this:
```
W tensorflow/stream_executor/platform/default/dso_loader.cc:64] Could not load dynamic library 'cudart64_110.dll'; dlerror: cudart64_110.dll not found
2022-05-26 20:24:21.906286: I tensorflow/stream_executor/cuda/cudart_stub.cc:29] Ignore above cudart dlerror if you do not have a GPU set up on your machine.
```
If you don't have a GPU, this is not a problem. If you do, your configuration is incorrect and you need to try reinstalling drivers and the correct version of CUDA for your system.