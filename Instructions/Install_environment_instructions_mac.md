# How to install CellProfiler from source with all plugins on Mac OS

1. **Download and install [Java JDK 11](https://adoptium.net/temurin/releases/?version=11)**
   
   <img src="https://user-images.githubusercontent.com/28116530/184950214-ca9d8d07-ab66-45f2-9a18-fb220bd0a8ec.png" width=500px/>

   After you download the file, open the installer and proceed through the steps to install Java 11.
   
    &nbsp;


2. **Download and install or update conda**

   For beginners, we recommend you use Anaconda Navigator since it is more beginner-friendly, but you can also use miniconda. [Download Anaconda](https://www.anaconda.com/products/distribution) from the website and install.

   **NOTE**: if you already have conda, you can get the command to update conda by typing `conda update` on your command line. The command will generally look like:

   `conda update --prefix /Users/USERNAME/opt/anaconda3 anaconda`

   &nbsp;
   
3. **Clone the CellProfiler-plugins Repo**

    Download a copy of (aka "clone") the CellProfiler-plugins repo from [here](https://github.com/CellProfiler/CellProfiler-plugins.git). You can download the whole repo by cloning it with git or simply clicking the green **Code** button on [the repo page](https://github.com/CellProfiler/CellProfiler-plugins.git) and selecting **Download ZIP** (see below).

   <img src="images/Install_environment_instructions_windows/2022-06-02T21-39-05.png" width="500"/>

    You can also use git or GitHub Desktop to clone the repo if you prefer.
    
   &nbsp;

4. **Create the environment from the .yml file**

   Open Anaconda Navigator and select the **Environments** tab on the left. We recommend you create the environment from the command line. To do this, Select the play button next to your base (root) environment and select **Open Terminal**:

   <img src="images/Install_environment_instructions_windows/2022-06-02T21-11-49.png" width="500"/>

   A black box should pop up with a blinking cursor. This is your terminal. You now need to navigate to where the **cellprofiler_plugins_mac.yml** file is inside of the CellProfiler-plugins folder you downloaded in the last step. This file is in the `Instructions` subfolder. Here is how we recommend you do this:
    1) In Finder, open the folder you downloaded in the previous step (usually called "CellProfiler-plugins-master") 
    2) There should be a folder called **Instructions**. Right click or ctrl+click that folder. Then hold down the option key (or Alt) on your keyboard. An option to **Copy "Instructions" as Pathname** should appear. Select this option

    <img width="509" alt="image" src="https://user-images.githubusercontent.com/28116530/184949743-901ada5e-dbe5-40d6-99c2-ad0877bddc31.png">

   3) Go back to your terminal and type `cd PATH_TO_FOLDER` where `PATH_TO_FOLDER` is the address you copied in the previous step. Press Enter.
  
   &nbsp;
   
   Now that you're in the right place, copy and paste this command into the terminal and press Enter.
   ```
   conda env create -f CellProfiler_plugins_mac.yml
   ```
   &nbsp;
   

 5. Activate your environment

    In your terminal, enter `conda activate CellProfiler_plugins` to activate your environment

 6. Verify that cellprofiler is installed correctly by running it from the command line.

    In your terminal, type in `pythonw -m cellprofiler` and hit Enter. this will open CellProfiler or will give you an error message.

 7. Install other packages for other plugins (just for RunStarDist)

    In terminal with your environment activated, enter:
    ```
    pip install stardist csbdeep --no-deps
    ```
    
    
    
    If you would like to use the omnipose models in cellpose, ensure you have cellpose 1.0.2 (you should by default if you've used our environment yml) and enter on the command line (in your activated environment):

    ```
    pip install omnipose
    ```

 8. Connect CellProfiler and the plugins repo

    With your environment active, type `pythonw -m cellprofiler` in terminal to open CellProfiler if it is not open already.

  * In CellProfiler, go to **File** then **Preferences...**
  * Scroll down and look for "CellProfiler Plugins Directory" on the left.
  * Select the **Browse** button and choose the folder where you extracted the CellProfiler plugins files. It is probably called "CellProfiler-plugins-master" unless you have renamed it.
  * Select **Save** at the bottom of the Preferences window
  * Close CellProfiler and reopen it by typing `pythonw -m cellprofiler` on the command line


  **NOTE**: You might get a warning like this:
  ```
  W tensorflow/stream_executor/platform/default/dso_loader.cc:64] Could not load dynamic library 'cudart64_110.dll'; dlerror: cudart64_110.dll not found
  2022-05-26 20:24:21.906286: I tensorflow/stream_executor/cuda/cudart_stub.cc:29] Ignore above cudart dlerror if you do not have a GPU set up on your machine.
  ```
  If you don't have a GPU, this is not a problem. If you do, your configuration is incorrect and you need to try reinstalling drivers and the correct version of CUDA for your system.

 9. Verify that the installation worked

    Add a module to your pipeline by hitting the **+** button in the pipeline panel (bottom left)

    In the "Add Modules" window that pops up, type "run" into the search bar. You should be able to see plugins like RunCellpose and RunStarDist if the installation was successful:
    ![](images/Install_environment_instructions_windows/2022-06-02T21-43-56.png)

   ---


## Common errors

1. My wheels are failing to build

- If you get a message like "ERROR: Failed building wheel for pyzmq" this usually means that you do not have pyzmq installed. Try to reinstall pyzmq.

2. Java virtual machine cannot be found

- If you're getting errors about Java, it means that java is not being configured properly on your system.
- Make sure you have installed The Java Development Kit 11 [here](https://adoptopenjdk.net/). Note that newer versions may not work.
- Make sure you've added environment variables at the **System** level and not at the **User** level. 
```
brew install java

# For the system Java wrappers to find this JDK, symlink it with
sudo ln -sfn /opt/homebrew/opt/openjdk/libexec/openjdk.jdk /Library/Java/JavaVirtualMachines/openjdk.jdk

# Set version in zshrc
echo export JAVA_HOME=$(/usr/libexec/java_home -v 1.8) >> ~/.zshrc
source ~/.zshrc
```

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


---
