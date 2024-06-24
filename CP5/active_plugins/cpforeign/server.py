import zmq
import numpy as np
import logging

HELLO = "Hello"
ACK = "Acknowledge"
DENY = "Deny"
CANCEL = "Cancel"

class ForeignToolError(Exception):
    pass

def _receive_ack(socket, logger, subject=None):
    ack = socket.recv_string()
    if ack == ACK:
        if subject:
            logger.debug(f"received ack for {subject}")
        else:
            logger.debug("received ack")
        return True
    elif ack == DENY:
        raise ForeignToolError("denied, aborting")
    elif ack == CANCEL:
        raise ForeignToolError("canceled, aborting")
    else:
        raise ForeignToolError("unexpected response", ack)

def _send_ack(socket, logger, subject):
    if subject:
        logger.debug(f"sending ack for {subject}")
    else:
        logger.debug("sending ack")
    socket.send_string(ACK)

class ForeignToolServer(object):
    def __init__(self, port, domain='*', protocol='tcp', wait_for_handshake=True):
        """
        Launch a server on the given port.
        """
        self._logger = logging.getLogger(f"{__name__} [server]")

        self._context = zmq.Context()
        self._server_socket = self._context.socket(zmq.PAIR)
        self._server_socket.bind(f"{protocol}://{domain}:{port}")
        self._logger.info("launched on", self._server_socket.getsockopt(zmq.LAST_ENDPOINT))

        if wait_for_handshake:
            self.wait_for_handshake()

    def wait_for_handshake(self):
        self._logger.debug("waiting for handshake from cllient")
        client_hello = self._server_socket.recv_string()
        if client_hello == HELLO:
            self._logger.debug("received correct handshake")
            _send_ack(self._server_socket, self._logger, subject="handshake")
        else:
            self._logger.debug("received incorrect handshake", client_hello)
            self._logger.debug("sending deny")
            self._server_socket.send_string(DENY)
            raise ForeignToolError("server received incorrect handshake")

    def _serve_image(self, image_data):
        """
        Serve an image to the client.
        """
        header = np.lib.format.header_data_from_array_1_0(image_data)

        self._logger.debug("sending header", header, "waiting for acknowledgement")
        self._server_socket.send_json(header)

        ack = _receive_ack(self._server_socket, self._logger, subject="header")

        self._logger.debug("sending image data", image_data.shape, "waiting for acknowledgement")
        
        self._server_socket.send(image_data, copy=False)

        ack = _receive_ack(self._server_socket, self._logger, subject="image data")
        
        labels_header = self._server_socket.recv_json()

        ack = _send_ack(self._server_socket, self._logger, subject="return header")

        label_bytes = self._server_socket.recv(copy=False)

        self._logger.debug("received label byte data")

        self._logger.debug("parsing label data")
        labels = np.frombuffer(label_bytes, dtype=labels_header['descr'])
        labels.shape = labels_header['shape']
        self._logger.debug("parse label data", labels.shape)
        
        _send_ack(self._server_socket, self._logger, subject="return data")
        
        return labels

    def serve_one_image(self, image_data):
        """
        Serve an image to the client.
        """
        return self._serve_image(image_data)

class ForeignToolClient(object):
    def __init__(self, port, domain='*', protocol='tcp', do_handshake=True, cb=None):
        """
        Connect to a server on the given port.
        """
        self._logger = logging.getLogger(f"{__name__} [client]")

        self._context = zmq.Context()
        self._client_socket = self._context.socket(zmq.PAIR)
        self._client_socket.connect(f"{protocol}://{domain}:{port}")
        self._logger.info("connected to", self._client_socket.getsockopt(zmq.LAST_ENDPOINT))

        if cb:
            self.register_cb(cb)

        if do_handshake:
            self.do_handshake()

        def do_handshake(self):
            """
            Handshake with the server.
            """
            self.client_socket.send_string(HELLO)
            response = _receive_ack(self.client_socket, self.logger, subject="handshake")

    def register_cb(self, cb):
        """
        Register a callback to be executed on the server.
        Must be run before receeive_image
        """
        self._cb = cb

    def _execute_cb(self, im, header):
        """
        Execute the callback on the server.
        """
        return self._cb(im, header)

    def _receive_image(self):
        """
        Receive an image from the server.
        """
        header = self._client_socket.recv_json()
        self._logger.debug("received header", header)

        _send_ack(self._client_socket, self._logger, subject="header")

        im_bytes = self._client_socket.recv(copy=False)
        self._logger.debug("received image bytes")

        self._logger.debug("parsing image data")
        buf = memoryview(im_bytes)
        im = np.frombuffer(buf, dtype=header['descr'])
        im = (im * 255).astype(np.uint8)
        im.shape = header['shape']
        self._logger.debug("parsed image data", im.shape)

        _send_ack(self._client_socket, self._logger, subject="image data")

        self._logger.debug("executing callback")
        return_data = self._execute_cb(im, header)
        self._logger.debug("executed callback")

        return_header = np.lib.format.header_data_from_array_1_0(return_data)
        self._logger.debug("returning header", return_header)
        self._client_socket.send_json(return_header)

        ack = _receive_ack(self._client_socket, self._logger, subject="return header")

        self._logger.debug("returning data")
        self._client_socket.send(return_data, copy=False)
        
        ack = _receive_ack(self._client_socket, self._logger, subject="return data")

    def receive_one_image(self):
        """
        Receive a single image from the server.
        """
        self._receive_image()

    def receive_images(self):
        """
        Receive images from the server.
        """
        while True:
            try:
                self._receive_image()
            except ForeignToolError:
                break
