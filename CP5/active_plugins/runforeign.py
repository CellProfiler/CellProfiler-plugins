import zmq
import numpy as np

from cellprofiler_core.module.image_segmentation import ImageSegmentation
from cellprofiler_core.setting.do_something import DoSomething
from cellprofiler_core.setting.text import Integer
from cellprofiler_core.object import Objects

HELLO = "Hello"
ACK = "Acknowledge"
DENIED = "Denied"

__doc__ = """\
RunForeign
============

**RunForeign** runs a foreign tool via sockets.


Assumes there is a server up and running, handshakes, and pings for availability on every validation run of pipeline.
Server must be idompotent on both handshake and validation ping.
Server provides definition of what run will be.

|

============ ============ ===============
Supports 2D? Supports 3D? Respects masks?
============ ============ ===============
YES          NO            YES
============ ============ ===============

"""

class RunForeign(ImageSegmentation):
    category = "Object Processing"

    module_name = "RunForeign"

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
            self.context.destroy()
            self.server_socket = None

        self.context = zmq.Context()
        self.server_socket = self.context.socket(zmq.PAIR)
        self.server_socket.copy_threshold = 0
        c = self.server_socket.connect(socket_addr)
        
        print("Setup socket at", socket_addr, "connected to", c)
        
        self.server_socket.send_string(HELLO)
        response = self.server_socket.recv_string()
        
        if response == ACK:
            print("Received correct response", response)
        else:
            print("Received unexpected response", response)

    def do_server_execute(self, im_data):
        dummy_data = lambda: np.array([[]])

        socket = self.server_socket
        header = np.lib.format.header_data_from_array_1_0(im_data)
        
        socket.send_json(header)

        ack = socket.recv_string()
        if ack == ACK:
            print("header acknowledged:", ack)
        else:
            print("unexpected response", ack)
            return dummy_data()
        
        socket.send(im_data, copy=False)

        ack = socket.recv_string()
        if ack == ACK:
            print("image data acknowledged", ack)
        elif ack == DENIED:
            print("image data denied, aborting", ack)
            return dummy_data()
        else:
            print("unknown response to image data", ack)
            return dummy_data()
        
        return_header = socket.recv_json()
        print("received return header", return_header)

        print("acknowledging header reciept")
        socket.send_string(ACK)

        print("waiting for image data")

        label_data_buf = socket.recv(copy=False)
        labels = np.frombuffer(label_data_buf, dtype=return_header['descr'])
        labels.shape = return_header['shape']
        print("returning label data", labels.shape)
        return labels