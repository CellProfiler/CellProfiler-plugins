# How to use the batch file: 
* On a WINDOWS computer, download the zip folder called **Install_CellProfiler_with_plugins.zip**
* Put the folder on your desktop
* Extract the contents
* Right click file called "install_cellprofiler_plugins.bat" and select "Run as Administrator"
  * You may get a security warning when running the batch file. Press More Info, then Run Anyway to proceed.
  * The script will run through a series of checks and steps. After it finishes each step, it will prompt you to press a key to continue. If it quits before reaching the end, the script has encountered an error. The steps are summarized below in "How the batch file works"
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
You can also always open CellProfiler by going to your start menu or list of programs and searching for "Anaconda Prompt (miniconda3)." Select this program to open a terminal and then type in `conda activate CP_plugins` then `pip install javabridge` and this will perform the installation. Then you can type in `cellprofiler` and it will open CellProfiler. 


# Potential errors
When you try to run CellProfiler, you might see an error. Here are common errors and solutions: 
```
Traceback (most recent call last):
  File "C:\tools\miniconda3\envs\CP_plugins\lib\runpy.py", line 194, in _run_module_as_main
    return _run_code(code, main_globals, None,
  File "C:\tools\miniconda3\envs\CP_plugins\lib\runpy.py", line 87, in _run_code
    exec(code, run_globals)
  File "C:\tools\miniconda3\envs\CP_plugins\Scripts\cellprofiler.exe\__main__.py", line 4, in <module>
  File "C:\tools\miniconda3\envs\CP_plugins\lib\site-packages\cellprofiler\__main__.py", line 13, in <module>
    import bioformats.formatreader
  File "C:\tools\miniconda3\envs\CP_plugins\lib\site-packages\bioformats\__init__.py", line 21, in <module>
    import javabridge
  File "C:\tools\miniconda3\envs\CP_plugins\lib\site-packages\javabridge\__init__.py", line 38, in <module>
    from .jutil import start_vm, kill_vm, vm, activate_awt, deactivate_awt
  File "C:\tools\miniconda3\envs\CP_plugins\lib\site-packages\javabridge\jutil.py", line 150, in <module>
    os.environ["PATH"] = os.environ["PATH"] + os.pathsep + _find_jvm() + \
  File "C:\tools\miniconda3\envs\CP_plugins\lib\site-packages\javabridge\jutil.py", line 139, in _find_jvm
    raise JVMNotFoundError()
javabridge.jutil.JVMNotFoundError: Can't find the Java Virtual Machine
```

If you see this error, first verify that Java is installed. There should be a folder in C:/Program Files called **Java-jdk-11**. If not, the installation has failed. Also check your Environment Variables (Windows 10 or below, type "Environment variable" into the search bar. Windows 11: Go to Control Panel > System > Advanced system settings > Environment Variables) and ensure that JAVA_HOME and JDK_HOME are in the System Variables (second box) and both are set to the location of the Java-jdk-11 folder. You can always manually download java jdk 11 from [Adoptium's website](https://adoptium.net/temurin/releases/?version=11). Assuming you have java installed and you still get this error, the solution is to install javabridge, which appears to be necessary for some Windows computers. Go to your start menu or list of programs and search for "Anaconda Prompt (miniconda3)" and then type in `conda activate CP_plugins` then `pip install javabridge` and this will perform the installation. Then you can type in `cellprofiler` and it will open CellProfiler. 
