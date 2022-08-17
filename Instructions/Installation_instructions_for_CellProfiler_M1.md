 Installation instructions for CellProfiler + plugins using a conda environment on Macs using the new Apple M1/2 processor. 


 Install CellProfiler inside a conda environment
   - For less conflict problems, it is recommended to follow the conda installation


1. **Install brew**
    ```
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    ```

2. **Update brew**
    ```
    brew update
    ```
    
3. **Install Java**
    ```
    brew install java
    ```

4. **For the system Java wrappers to find this JDK, symlink it with**
    ```
    sudo ln -sfn /opt/homebrew/opt/openjdk/libexec/openjdk.jdk /Library/Java/JavaVirtualMachines/openjdk.jdk
    ```

5. **Set version in zshrc**
    ```
    echo export JAVA_HOME=$(/usr/libexec/java_home -v 1.8) >> ~/.zshrc
    source ~/.zshrc
    ```

6. **Brew install the packages req**
    ```
    brew install freetype mysql
    ```

7. **Direct to brew openssl**
    ```
    export LDFLAGS="-L$(brew --prefix)/opt/openssl/lib"
    ```

8. **Install hdf5**
    ```
    brew install hdf5@1.12
    ```

9. **Make sure to get the version directory correct for the version installed. Find with `ls /opt/homebrew/Cellar/hdf5/`**
    ```
    export HDF5_DIR=/opt/homebrew/Cellar/hdf5/1.12.1_1/
    ```
10. **Create a folder and download cellprofiler, cellprofiler-core, cellprofiler-plugins and wxPython**

```
Download CellProfiler-core https://github.com/CellProfiler/core
```
```
Download CellProfiler https://github.com/CellProfiler/CellProfiler
```
```
Download CellProfiler-plugins https://github.com/CellProfiler/CellProfiler-plugins
```
```
1. Download dev build of wxPython here: https://wxpython.org/Phoenix/snapshot-builds/
2. Download the latest build with the filename format: wxPython-4.1.2a1.devXXXX+XXXXXXXX.tar.gz
      - Ignore the `.whl` files
3. Then, extract wxPython.
```

11. **Modify the **setup.py** in the cloned CellProfiler repo.**
   - Comment out cellprofiler-core and wxpython from the **install_requires** section, since we are installing our own versions from source:
    ```
    ...
    "boto3>=1.12.28",
    # "cellprofiler-core==4.2.1",
    "centrosome==1.2.0",
    ...
    "six",
    # "wxPython==4.1.0",
    ```
12. **Download and install or update conda/miniconda**

   For beginners, we recommend you use Anaconda Navigator since it is more beginner-friendly, but you can also use miniconda. [Download Anaconda](https://www.anaconda.com/products/distribution) from the website and install.

   **NOTE**: if you already have conda, you can get the command to update conda by typing `conda update` on your command line. The command will generally look like:

   `conda update --prefix /Users/USERNAME/opt/anaconda3 anaconda`

13. **Create a conda environment using the cellprofiler_plugins_macM1.yml file**

In the terminal, navigate to where your environment file is located with "cd PATH_TO_FOLDER" where "PATH_TO_FOLDER" is the path to the directory containing your yml file (e.g., /User/USER/FOLDER/cellprofiler-plugins/instructions).
    ```
    conda env create -n cp_plugins --file cellprofiler_plugins_macM1.yml
    ```

14. **Activate the conda environment**

    ```
    conda activate cp_plugins
    ```

15. **Install wxPython, core and cellprofiler**

In the terminal with your environment activate, navigate to the folder where you download the softwares and enter:

Remeber to change the wxPython-name to mach your folder.
    
```
pip install ./wxPython-4.2.1a1.dev5486+98871b69 
pip install ./core
pip install ./CellProfiler
```

16. **Resolving dependencies conflits**

In the terminal with your environment activate, enter:
```
pip uninstall -y centrosome python-javabridge
pip install --no-cache-dir --no-deps --no-build-isolation python-javabridge centrosome
pip uninstall matplotlib -y
pip install matplotlib==3.2
pip uninstall mahotas
pip install mahotas
```

17. **Install other packages for other plugins (just for runStardist)**

In the terminal with your environment activate, enter:
```
conda install -c apple tensorflow-deps
python -m pip install tensorflow-macos
pip install stardist csbdeep --no-deps
```

18. **Open CellProfiler**
    - Execute this command from within the downloaded CellProfiler repo (get there with `cd CellProfiler`)

    ```
    pythonw -m cellprofiler
    ```

19. **Connect CellProfiler and the plugins repo**

With your environment active, type pythonw -m cellprofiler in terminal to open CellProfiler if it is not open already.

*In CellProfiler, go to File then Preferences...
*Scroll down and look for "CellProfiler Plugins Directory" on the left.
*Select the Browse button and choose the folder where you extracted the CellProfiler plugins files. It is probably called "CellProfiler-plugins-master" unless you have renamed it.
*Select Save at the bottom of the Preferences window
*Close CellProfiler and reopen it by typing pythonw -m cellprofiler on the command line

20. **Verify that the installation worked**

- Execute this command from within the downloaded CellProfiler repo (get there with `cd CellProfiler`)

    ```
    pythonw -m cellprofiler
    ```

Add a module to your pipeline by hitting the **+** button in the pipeline panel (bottom left)

In the "Add Modules" window that pops up, type "run" into the search bar. You should be able to see plugins like RunCellpose and RunStarDist if the installation was successful:
![](images/Install_environment_instructions_windows/2022-06-02T21-43-56.png)