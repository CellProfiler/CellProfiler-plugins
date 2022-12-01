Installation instructions for CellProfiler, CellProfiler plugins, CellPose and StarDist in a conda environment on Apple silicon.

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

4. **For the system Java wrappers to find this JDK and symlink it**
    ```
    sudo ln -sfn /opt/homebrew/opt/openjdk/libexec/openjdk.jdk /Library/Java/JavaVirtualMachines/openjdk.jdk
    ```

5. **Set version in .zshrc**
    ```
    echo export JAVA_HOME=$(/usr/libexec/java_home -v 1.8) >> ~/.zshrc
    source ~/.zshrc
    ```

6. **Brew install package requirements**
    ```
    brew install freetype mysql git
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
10. **Create a folder and download cellprofiler-plugins**

    ```
    mkdir cp_plugins
    cd cp_plugins
    git clone https://github.com/CellProfiler/CellProfiler-plugins
    ```

11. **Download and install miniconda**

   ```
    wget https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-arm64.sh -O ~/miniconda.sh
   ```


12. **Create a conda `.yml` file**
    In a text editor, paste the following test and save it as `cellprofiler_plugins_macM1.yml`:
    ```
    name: cpcellpose

    channels:
    - conda-forge
    - anaconda
    - bioconda
    - defaults
    - apple

    dependencies:
    - python=3.8
    - pip
    - h5py
    - mysqlclient
    - imagecodecs
    - python.app
    - pandas
    - pip:
        - cellpose
        - attrdict
        - sip==5.5.0
        - boto3>=1.12.28
        - cellprofiler-core
        - centrosome==1.2.1
        - docutils==0.15.2
        - h5py~=3.6.0
        - imageio>=2.5
        - inflect>=2.1
        - Jinja2>=2.11.2
        - joblib>=0.13
        - mahotas>=1.4
        - matplotlib==3.1.3
        - mysqlclient==1.4.6
        - numpy>=1.20.1
        - Pillow>=7.1.0
        - prokaryote==2.4.4
        - python-bioformats==4.0.6
        - python-javabridge==4.0.3
        - pyzmq~=22.3
        - sentry-sdk==0.18.0
        - requests>=2.22
        - scikit-image>=0.17.2
        - scikit-learn>=0.20
        - scipy>=1.4.1
        - six
        - tifffile<2022.4.22
        - wxPython==4.2.0
    ```


13. **Create a conda environment using the cellprofiler_plugins_macM1.yml file**

    At this stage, your folder/file structure should look like this:

    ```
    ├── cp_plugins
        ├── CellProfiler-plugins
        └── cellprofiler_plugins_macM1.yml
    ```

    In the terminal, make sure you are in the `cp_plugins` folder mentioned above.

    ```
    conda env create -n cp_plugins --file cellprofiler_plugins_macM1.yml
    ```

14. **Activate the conda environment**

    ```
    conda activate cp_plugins
    ```

15. **Install Cellprofiler core and cellprofiler**

    In the terminal with your environment activate, navigate to the folder where you download the software and enter:
        
    ``` 
    pip install cellprofiler --no-deps
    ```

16. **Install other packages for other plugins (just for runStardist)**

    In the terminal with your environment activate, enter:
    ```
    conda install -c apple tensorflow-deps
    python -m pip install tensorflow-macos
    pip install stardist csbdeep --no-deps
    ```

17. **Open CellProfiler**

    Execute this command from within the downloaded CellProfiler repo (get there with `cd CellProfiler`)

    ```
    pythonw -m cellprofiler
    ```

18. **Connect CellProfiler with the plugins folder**

    With your environment active, type pythonw -m cellprofiler in terminal to open CellProfiler if it is not open already.

    *In CellProfiler, go to File then Preferences...
    *Scroll down and look for "CellProfiler Plugins Directory" on the left.
    *Select the Browse button and choose the folder where you extracted the CellProfiler plugins files. It is probably called "CellProfiler-plugins-master" unless you have renamed it.
    *Select Save at the bottom of the Preferences window
    *Close CellProfiler and reopen it by typing pythonw -m cellprofiler on the command line


### Resolving dependencies conflits

    In the terminal with your environment activate, enter:
    ```
    pip uninstall -y centrosome python-javabridge
    pip install --no-cache-dir --no-deps --no-build-isolation python-javabridge centrosome
    pip uninstall matplotlib -y
    pip install matplotlib==3.2
    pip uninstall mahotas -y
    pip install mahotas
    ```

### Test your installation

Add a module to your pipeline by hitting the **+** button in the pipeline panel (bottom left)

In the "Add Modules" window that pops up, type "run" into the search bar. You should be able to see plugins like RunCellpose and RunStarDist if the installation was successful:
![](images/Install_environment_instructions_windows/2022-06-02T21-43-56.png)
