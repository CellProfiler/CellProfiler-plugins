import os
from time import sleep

import appose
from appose.service import ResponseType
import numpy as np

from cellprofiler_core.module._module import Module
from cellprofiler_core.setting.do_something import DoSomething
from cellprofiler_core.setting.subscriber import ImageSubscriber
from cellprofiler_core.setting.text import Text

__doc__ = """\
ApposeDemo
============

**ApposeDemo** is a demo of runnin napari through Appose.


TODO: more docs

|

============ ============ ===============
Supports 2D? Supports 3D? Respects masks?
============ ============ ===============
YES          YES          YES
============ ============ ===============

"""

cite_paper_link = "https://doi.org/10.1016/1047-3203(90)90014-M"

qt_setup = """
# CRITICAL: Qt must run on main thread on macOS.

from qtpy.QtWidgets import QApplication
from qtpy.QtCore import Qt, QTimer
import threading
import sys

# Configure Qt for macOS before any QApplication creation
QApplication.setAttribute(Qt.AA_MacPluginApplication, True)
QApplication.setAttribute(Qt.AA_PluginApplication, True)
QApplication.setAttribute(Qt.AA_DisableSessionManager, True)

# Create QApplication on main thread.
qt_app = QApplication(sys.argv)

# Prevent Qt from quitting when last Qt window closes; we want napari to stay running.
qt_app.setQuitOnLastWindowClosed(False)

task.export(qt_app=qt_app)
task.update()

# Run Qt event loop on main thread.
qt_app.exec()
"""

qt_shutdown = """
# Signal main thread to quit.
qt_app.quit()
"""

napari_show = """
import napari
import numpy as np

from superqt import ensure_main_thread

@ensure_main_thread
def show(narr):
    napari.imshow(narr)

show(ndarr.ndarray())
task.outputs["shape"] = ndarr.shape
"""

READY = False

class ApposeDemo(Module):
    category = "Image Processing"

    module_name = "ApposeDemo"

    variable_revision_number = 1

    def create_settings(self):
        super().create_settings()

        self.x_name = ImageSubscriber(
            "Select the input image", doc="Select the image you want to use."
        )
        
        self.package_path = Text(
            "Path to apposednapari environment",
            f"{os.path.dirname(__file__)}/apposednapari/.pixi/envs/default",
        )
        self.doit = DoSomething(
            "Do the thing",
            "Do it",
            lambda: self.send_to_napari(),
            doc=f"""\
Press this button to do the job.
""",
        )

    def settings(self):
        return super().settings() + [self.x_name, self.package_path, self.doit]
    
    def visible_settings(self):
        return self.settings()
    
    def volumetric(self):
        return True

    def run(self, workspace):
        x_name = self.x_name.value

        images = workspace.image_set

        x = images.get_image(x_name)

        x_data = x.pixel_data

        self.send_to_napari(x_data)

        if self.show_window:
            ...

    # credit to Curtis Rueden:
    # https://github.com/ctrueden/appose-napari-demo/blob/a803e50347a023578afdd9ddc2c287567d5445fc/napari-show.py
    def send_to_napari(self, img_data=None):
        env = appose.base(str(self.package_path)).build()
        with env.python() as python:
            # Print Appose events verbosely, for debugging purposes.
            python.debug(print)

            # Start the Qt application event loop in the worker process.
            print("Starting Qt app event loop")
            setup = python.task(qt_setup, queue="main")
            def check_ready(event):
                if event.response_type == ResponseType.UPDATE:
                    print("Got update event! Marking Qt as ready")
                    global READY
                    READY = True
                    print("Ready...", READY)
            print("attempting to start to listen")
            setup.listen(check_ready)
            print("attempting start setup")
            setup.start()
            print("Waiting for Qt startup...")
            global READY
            while not READY:
                #print("sleeping", READY)
                sleep(0.1)
            print("Qt is ready!")

            if img_data is None:
                img_data = np.random.random([512, 384]).astype("float64")

            # Create a test image in shared memory.
            ndarr = appose.NDArray(dtype=str(img_data.dtype), shape=img_data.shape)
            # There's probably a slicker way without needing to slice/copy...
            ndarr.ndarray()[:] = img_data[:]

            # Actually do a real thing with napari: create and show an image.
            print("Showing image with napari...")
            task = python.task(napari_show, inputs={"ndarr": ndarr})

            task.wait_for()
            shape = task.outputs["shape"]
            print(f"Task complete! Got shape: {shape}")
