# How to use the batch file: 
* On a WINDOWS computer, download the zip folder called **Install_CellProfiler_with_plugins.zip**
* Put the folder on your desktop
* Extract the contents
* Right click file called "install_cellprofiler_plugins.bat" and select "Run as Administrator"
  * It will do some checks for you. Once chocolatey is ready, it will prompt you to hit a key to proceed. Press any key.
  * Then it will handle installation for you (see below). This takes 15-20 minutes depending on your internet connection.
* After installation finishes, you can open CellProfiler by double clicking the batch file run_cellprofiler.bat
* The only thing you have to configure is in CellProfiler, go to **File** > **Preferences** and scroll down to the **CellProfiler plugins folder** option and set this to the location of your CellProflier-plugins folder (it should be in your Downloads folder). See below: 
<p align="center">
<img width="500" alt="image" src="https://user-images.githubusercontent.com/28116530/182713252-d1403ace-a70a-400a-8f34-7e80f7cf172e.png">
</p>

* Close and re-open CellProfiler and you should have plugins available. 


# How the batch file works:
* The beginning checks if you're in administrator mode (necessary for chocolatey)
* The next part uses powershell to download chocolatey and install it (if it isn't already installed)
* Then packages are installed the same way as from the command line with `choco install package-name`
* Next we check if the system has conda available and if not, add miniconda paths to the system-level PATH
* Next we use powershell to download OpenJDK 11 from adoptium. This step takes some minutes (~5). After downloading, this .ps1 file will install java to C:/Program Files/Java-jdk-11 and then add JAVA_HOME and JDK_HOME system environment variables
* Next we move into the Downloads folder and if a CellProfiler-plugins folder isn't there, it will download a copy of the repo to the Downloads folder
  * The folder is extracted and the original .zip file removed
* Finally we use miniconda to create a new CP_plugins environment from the .yml file in the CellProfiler-plugins folder and perform necessary additional installs

There is a separate batch file that just activates the conda environment and opens CellProfiler (so the user doesn't have to type anything into the command line)
