import shlex
import sys
import os
import re
import subprocess
import threading
import logging

from cellprofiler_core.module.image_segmentation import ImageSegmentation
from cellprofiler_core.setting.text import Text
from cellprofiler_core.setting.text import Filename
from cellprofiler_core.setting.text import Integer
from cellprofiler_core.object import Objects

from cpforeign.server import ForeignToolServer

LOGGER = logging.getLogger(__name__)

HELLO = "Hello"
ACK = "Acknowledge"
DENIED = "Denied"

__doc__ = """\
RunForeignEnv
============

**RunForeign** runs a foreign tool, in a foreign (conda) environment, via sockets.


Assumes there is a client up and running.

|

============ ============ ===============
Supports 2D? Supports 3D? Respects masks?
============ ============ ===============
YES          NO            YES
============ ============ ===============

"""

def _run_logger(workR):
    # this thread shuts itself down by reading from worker's stdout
    # which either reads content from stdout or blocks until it can do so
    # when the worker is shut down, empty byte string is returned continuously
    # which evaluates as None so the break is hit
    # I don't really like this approach; we should just shut it down with the other
    # threads explicitly
    while True:
        try:
            print('reading')
            line = workR.stdout.readline()
            if (type(line) == bytes):
                line = line.decode("utf-8")
            if not line:
                break
            log_msg_match = re.match(fr"{workR.pid}\|(10|20|30|40|50)\|(.*)", line)
            if log_msg_match:
                levelno = int(log_msg_match.group(1))
                msg = log_msg_match.group(2)
            else:
                levelno = 20
                msg = line

            LOGGER.log(levelno, "\n\r  [Worker (%d)] %s", workR.pid, msg.rstrip())

        except Exception as e:
            LOGGER.exception(e)
            break


class RunForeignEnv(ImageSegmentation):
    category = "Object Processing"

    module_name = "RunForeignEnv"

    variable_revision_number = 1

    def create_settings(self):
        super().create_settings()
        
        self._server = None
        self._client_launched = False

        self.server_port = Integer(
            text="Server port number",
            value=7878,
            minval=0,
            doc="""\
The port number which the server is listening on. The server must be launched manually first.
""",
        )
        
        self.env_name = Text(text="Conda environment name", value="foreign-thresh")
        
        self.algo_path = Filename(text="Algorithm path", value="/Users/ngogober/Developer/CellProfiler/CellProfiler-plugins/CP5/active_plugins/cpforeign/thresh.py")

    def settings(self):
        return super().settings() + [self.server_port, self.env_name, self.algo_path]
    
    # ImageSegmentation defines this so we have to overide it
    def visible_settings(self):
        return self.settings()
    
    # ImageSegmentation defines this so we have to overide it
    def volumetric(self):
        return False

    def prepare_run(self, workspace):

        LOGGER.debug(">>> Preparing run")
        if not self._server:
            LOGGER.debug(">>> Initializing server")
            self._server = ForeignToolServer(self.server_port.value, wait_for_handshake=False)

        if not self._client_launched:
            LOGGER.debug(">>> Launching client")
            command = f"conda run --no-capture-output -n {self.env_name.value} python {self.algo_path.value}"
            args = shlex.split(command)
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            self._client_proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stdout, bufsize=1, universal_newlines=True, env=env, close_fds=False)
            #self._client_thread = threading.Thread(target=_run_logger, args=(self._client_proc,), name="foreign client stdout logger thread")
            #self._client_thread.start()

            self._client_launched = True
            self._server.wait_for_handshake()

        return True

    def post_run(self, workspace):
        if self._client_launched:
            LOGGER.debug(">>> Shuttding down client")
            #self._client_thread.join()
            self._client_proc.terminate()

    def run(self, workspace):
        # TODO: is this supposed to not run in test mode? because it doesn't...
        self.prepare_run(workspace)

        x_name = self.x_name.value

        y_name = self.y_name.value

        images = workspace.image_set

        x = images.get_image(x_name)

        dimensions = x.dimensions

        x_data = x.pixel_data

        y_data = self._server.serve_one_image(x_data)

        y = Objects()

        y.segmented = y_data

        y.parent_image = x.parent_image

        objects = workspace.object_set

        objects.add_objects(y, y_name)

        self.add_measurements(workspace)

        if self.show_window:
            workspace.display_data.x_data = x_data

            workspace.display_data.y_data = y_data

            workspace.display_data.dimensions = dimensions
