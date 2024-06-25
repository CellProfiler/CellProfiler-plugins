import zmq
import numpy as np
import logging

from cellprofiler_core.module.image_segmentation import ImageSegmentation
from cellprofiler_core.setting.do_something import DoSomething
from cellprofiler_core.setting.text import Integer
from cellprofiler_core.object import Objects

LOGGER = logging.getLogger(__name__)

HELLO = "Hello"
ACK = "Acknowledge"
DENIED = "Denied"

__doc__ = """\
RunForeignNb
============

**RunForeign** runs a foreign notebook via sockets.


Assumes there is a notebook running as a server to do the handshake, receive an image, and send back labels.

|

============ ============ ===============
Supports 2D? Supports 3D? Respects masks?
============ ============ ===============
YES          NO            YES
============ ============ ===============

"""

class RunForeignNb(ImageSegmentation):
    category = "Object Processing"

    module_name = "RunForeignNb"

    variable_revision_number = 1

    def create_settings(self):
        super().create_settings()
        
        self.context = None
        self.server_socket = None

        # TODO: launch server automatically, if necessary
        self.server_port = Integer(
            text="Server port number",
            value=7878,
            minval=0,
            doc="""\
The port number which the server is listening on. The server must be launched manually first.
""",
        )

        # TODO: perform handshake automatically, if necessary
        self.server_handshake = DoSomething(
            "",
            "Perform Server Handshake",
            self.do_server_handshake,
            doc=f"""\
Press this button to do an initial handshake with the server.
This must be done manually, once.
""",
        )

    def settings(self):
        return super().settings() + [self.server_port, self.server_handshake]
    
    # ImageSegmentation defines this so we have to overide it
    def visible_settings(self):
        return self.settings()
    
    # ImageSegmentation defines this so we have to overide it
    def volumetric(self):
        return False

    def run(self, workspace):
        x_name = self.x_name.value

        y_name = self.y_name.value

        images = workspace.image_set

        x = images.get_image(x_name)

        dimensions = x.dimensions

        x_data = x.pixel_data

        y_data = self.do_server_execute(x_data)

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

    def do_server_handshake(self):
        port = str(self.server_port.value)
        domain = "localhost"
        socket_addr = f"tcp://{domain}:{port}"

        if self.context:
            LOGGER.debug("destroying existing context")
            self.context.destroy()
            self.server_socket = None

        self.context = zmq.Context()
        self.server_socket = self.context.socket(zmq.PAIR)
        self.server_socket.copy_threshold = 0
        
        LOGGER.debug(f"connecting to {socket_addr}")

        c = self.server_socket.connect(socket_addr)
        
        LOGGER.debug(f"setup socket at {c}")
        
        LOGGER.debug("sending handshake, waiting for acknowledgement")

        self.server_socket.send_string(HELLO)
        
        poller = zmq.Poller()
        poller.register(self.server_socket, zmq.POLLIN)
        while True:
            socks = dict(poller.poll(5000))
            if socks.get(self.server_socket) == zmq.POLLIN:
                break
            else:
                LOGGER.debug("handshake timeout")
                return

        response = self.server_socket.recv_string()

        if response == ACK:
            LOGGER.debug(f"received correct response {response}")
        else:
            LOGGER.debug(f"received unexpected response {response}")

    def do_server_execute(self, im_data):
        dummy_data = lambda: np.array([[]])

        socket = self.server_socket
        header = np.lib.format.header_data_from_array_1_0(im_data)

        LOGGER.debug(f"sending header {header}; waiting for acknowledgement")
        socket.send_json(header)

        ack = socket.recv_string()
        if ack == ACK:
            LOGGER.debug(f"header acknowledged: {ack}")
        else:
            LOGGER.debug(f"unexpected response {ack}")
            return dummy_data()
        
        LOGGER.debug(f"sending image data {im_data.shape}; waiting for acknowledgement")
        socket.send(im_data, copy=False)

        ack = socket.recv_string()
        if ack == ACK:
            LOGGER.debug(f"image data acknowledged {ack}")
        elif ack == DENIED:
            LOGGER.debug(f"image data denied, aborting {ack}")
            return dummy_data()
        else:
            LOGGER.debug(f"unknown response to image data {ack}")
            return dummy_data()

        LOGGER.debug("waiting for return header")
        return_header = socket.recv_json()
        LOGGER.debug(f"received return header {return_header}")

        LOGGER.debug("acknowledging header reciept")
        socket.send_string(ACK)

        LOGGER.debug("waiting for image data")
        label_data_buf = socket.recv(copy=False)
        LOGGER.debug("image data received")

        labels = np.frombuffer(label_data_buf, dtype=return_header['descr'])
        labels.shape = return_header['shape']
        LOGGER.debug(f"returning label data {labels.shape}")

        return labels
