# How to install CellProfiler from source with all plugins on Windows

1. Install Microsoft Visual Studio C++ build tools downloadable [here](   https://visualstudio.microsoft.com/visual-cpp-build-tools/)

   **NOTE**:Make sure to check 'Desktop development with C++' under Desktop and Mobile in the installer.

2. Install Microsoft Visual C++ Redistributable 2015-2022 downloadable [here]( https://docs.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist?view=msvc-170)

   Select the version appropriate for your architecture. On windows, you can determine this by going to **Control Panel** then selecting **All Control Panel Items** then **System** and the architecture of your processor will be included next to "System type:".

3. Install or update conda

   * Note: you can get the command to update conda by typing `conda update` on your command line. The command will generally look like:

   `conda update --prefix /Users/USERNAME/opt/anaconda3 anaconda`

   For beginners, we recommend you use Anaconda Navigator since it is more beginner-friendly. Download Anaconda from the website [here](https://www.anaconda.com/products/distribution), then open Anaconda Navigator

4. Try to create a new environment from the included .yml file

   **Warning, this step may take a while**

   Download the environment file [CellProfiler_plugins_windows.yml](FUTURE LINK)

   Within Anaconda Navigator, select the **Environments** tab on the left.

   Then select `Import`  <img src="images/Install_environment_instructions/file-import-solid.svg" data-canonical-src="images/Install_environment_instructions/file-import-solid.svg" width="20" height="20"/> then select the environment file you just downloaded.

   If this fails and an error message pops up, we recommend you try to create the environment from the command line. To do this, Select the play button next to your base(root) environment (IMAGE) and select **New Terminal**.

   Navigate to where your environment file is located with `cd PATH_TO_FOLDER` where `PATH_TO_FOLDER` is the path to the directory containing your yml file (e.g., C:/Users/USER/Desktop). If you are on windows, the path is available in the address bar of file explorer.

   Then in the terminal window that pops up, enter the following command:
   ```
   conda env create -f cellprofiler_plugins_min.yml
   ```

5. Activate your environment

  If you've installed Anaconda, go to the Environments tab, then select the play button next to your cellprofiler_plugins environment (IMAGE) and select **New Terminal**.

  Otherwise, open your terminal or command prompt and activate the environment with `conda activate cellprofiler_plugins`

6. Verify that cellprofiler is installed correctly by running it from the command line.

  In your terminal or command prompt, type in `cellprofiler` and hit Enter. this will open up CellProfiler or will give you an error message.

7. Install other packages for other plugins

  In terminal with your environment activated
  ```
  pip install stardist csbdeep --no-deps
  ```

8. Clone the CellProfiler-plugins Repo
  1. The repo can be found here: https://github.com/CellProfiler/CellProfiler-plugins.git
  2. On that page, select the green **code** button and then select **Download ZIP**. Choose where you want the files to be downloaded on your computer
  3. If on Windows, right click the zip folder and select **Extract All**. On Mac, double click the zip folder and it will be extracted

9. Connect CellProfiler and the plugins repo
  1. Go to your command prompt or terminal with your cellprofiler_plugins enironment activated and type `cellprofiler` to open CellProfiler
  2. In CellProfiler, go to **File** then **Preferences...**
  3. Scroll down and look for "CellProfiler Plugins Directory" on the left. Select the **Browse** button and choose the folder where you extracted the CellProfiler plugins files. It is probably called "CellProfiler-plugins-master" unless you have renamed it.
  4. Hit **Save** at the bottom of the Preferences window
  5. Close CellProfiler and reopen it by typing `cellprofiler` on the command line

  You might get a warning like this:
  ```
  W tensorflow/stream_executor/platform/default/dso_loader.cc:64] Could not load dynamic library 'cudart64_110.dll'; dlerror: cudart64_110.dll not found
2022-05-26 20:24:21.906286: I tensorflow/stream_executor/cuda/cudart_stub.cc:29] Ignore above cudart dlerror if you do not have a GPU set up on your machine.
  ```
  If you don't have a GPU, this is not a problem. If you do, your configuration is incorrect and you need to try reinstalling drivers and the correct version of CUDA for your system.

10. Verify that the installation worked
  1. Add a module to your pipeline by hitting the **+** button in the pipeline panel (bottom left)
  2. In the "Add Modules" window that pops up, type "run" into the search bar. Try to add runCellpose or runStarDist


## Common errors

1. My wheels are failing to build

- If you get a message like "ERROR: Failed building wheel for pyzmq" this usually means that you do not have the Microsoft Visual Studio tools installed. See Step # above and ensure that you have "Desktop development with C++" selected under the install configuration options

2. Java virtual machine cannot be found

- If you're getting errors about Java, it means that java is not being configured properly on your system.
- Make sure you have installed The Java Development Kit 11 (link). Note that newer versions may not work.
- Make sure you've added environment variables at the **System** level and not at the **User** level. You need to add both `JAVA_HOME` and `JDK_HOME` and both need to point to the folder that holds your jdk installation. Typically this path would look something like `C:\Program Files\Java\jdk-11.0.15.1` but it might be different on your machine depending on where you've installed Java.

3. Installing pyzmq failed

- You might get an error when trying to install pyzmq. Something like
```
ERROR: Command errored out with exit status 1:
```
And earlier in the traceback:
```
Fatal: Cython-generated file 'zmq\backend\cython\_device.c' not found.
                  Cython >= 0.20 is required to compile pyzmq from a development branch.
                  Please install Cython or download a release package of pyzmq.
```

  To fix this, `conda install cython`       

- You might also get an error like:
```
AttributeError: 'MSVCCompiler' object has no attribute '_vcruntime_redist'
```

  Generally, this error means that you don't have the right Microsoft Visual Studio C compiler. You can try two things:

  1. Look below in the code. Even if the wheel fails, pyzmq will still attempt to install. Look below for `Running setup.py install for pyzmq ... done`
  2. You can try using an older version of the Microsoft Visual C++ Redistributable Package. The install is verified for 2008 specifically, which can be downloaded here: https://www.microsoft.com/en-us/download/details.aspx?id=11895 though newer versions can still be used.



---
