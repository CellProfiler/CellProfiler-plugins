import atexit
import os
import logging
import tempfile

from cellprofiler_core.preferences import config_read_typed, get_headless, get_temporary_directory
from cellprofiler_core.preferences import get_omero_server, get_omero_port, get_omero_user
import omero
from omero.gateway import BlitzGateway
import omero_user_token

LOGGER = logging.getLogger(__name__)
OMERO_CREDENTIAL_FILE = os.path.join(get_temporary_directory(), "OMERO_CP.token")


def login(e=None, server=None, token_path=None):
    # Attempt to connect to the server, first using a token, then via GUI
    CREDENTIALS.get_tokens(token_path)
    if CREDENTIALS.tokens:
        if server is None:
            # URL didn't specify which server we want. Just try whichever token is available
            server = list(CREDENTIALS.tokens.keys())[0]
        connected = CREDENTIALS.try_token(server)
    else:
        connected = CREDENTIALS.client is not None
    if get_headless():
        if connected:
            LOGGER.info(f"Connected to {CREDENTIALS.server}")
        elif CREDENTIALS.try_temp_token():
            connected = True
            LOGGER.info(f"Connected to {CREDENTIALS.server}")
        else:
            LOGGER.warning("Failed to connect, was user token invalid?")
        return connected
    else:
        from .gui import login_gui
        login_gui(connected, server=None)


def get_temporary_dir():
    temporary_directory = get_temporary_directory()
    if not (
        os.path.exists(temporary_directory) and os.access(temporary_directory, os.W_OK)
    ):
        temporary_directory = tempfile.gettempdir()
    return temporary_directory


def clear_temporary_file():
    LOGGER.debug("Checking for OMERO credential file to delete")
    if os.path.exists(OMERO_CREDENTIAL_FILE):
        os.unlink(OMERO_CREDENTIAL_FILE)
        LOGGER.debug(f"Cleared {OMERO_CREDENTIAL_FILE}")


if not get_headless():
    if os.path.exists(OMERO_CREDENTIAL_FILE):
        LOGGER.warning("Existing credential file was found")
    # Main GUI process should clear any temporary tokens
    atexit.register(clear_temporary_file)


class LoginHelper:
    """
    This class stores our working set of OMERO credentials and connection objects.

    It behaves as a singleton, so multiple OMERO-using plugins will share credentials.
    """
    _instance = None

    def __new__(cls):
        # We only allow one instance of this class within CellProfiler
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self.server = get_omero_server()
        self.port = get_omero_port()
        self.username = get_omero_user()
        self.passwd = ""
        self.session_key = None
        self.session = None
        self.client = None
        self.gateway = None
        self.container_service = None
        self.tokens = {}
        # Any OMERO browser GUI which is connected to this object
        self.browser_window = None
        atexit.register(self.shutdown)

    def get_gateway(self):
        if self.client is None:
            raise Exception("Client connection not initialised")
        if self.gateway is None:
            LOGGER.debug("Constructing BlitzGateway")
            self.gateway = BlitzGateway(client_obj=self.client)
        return self.gateway

    def get_tokens(self, path=None):
        # Load all tokens from omero_user_token
        self.tokens.clear()
        # Future versions of omero_user_token may support multiple tokens, so we code with that in mind.
        # Check the reader setting which disables tokens.
        tokens_enabled = config_read_typed(f"Reader.OMERO.allow_token", bool)
        if tokens_enabled is not None and not tokens_enabled:
            return
        # User tokens sadly default to the home directory. This would override that location.
        py_home = os.environ['HOME']
        if path is not None:
            os.environ['HOME'] = path
        try:
            LOGGER.info("Requesting token info")
            token = omero_user_token.get_token()
            server, port = token[token.find('@') + 1:].split(':')
            port = int(port)
            LOGGER.info("Connection to {}:{}".format(server, port))
            session_key = token[:token.find('@')]
            self.tokens[server] = (server, port, session_key)
        except Exception:
            LOGGER.error("Failed to get user token", exc_info=True)
        if path is not None:
            os.environ['HOME'] = py_home

    def try_token(self, address):
        # Attempt to use an omero token to connect to a specific server
        if address not in self.tokens:
            LOGGER.error(f"Token {address} not found")
            return False
        else:
            server, port, session_key = self.tokens[address]
            return self.login(server=server, port=port, session_key=session_key)

    def create_temp_token(self):
        # Store a temporary OMERO token based on our active session
        # This allows the workers to use that session in Analysis mode.
        if self.client is None:
            raise ValueError("Client not initialised, cannot make token")
        if os.path.exists(OMERO_CREDENTIAL_FILE):
            LOGGER.warning(f"Token already exists at {OMERO_CREDENTIAL_FILE}, overwriting")
            os.unlink(OMERO_CREDENTIAL_FILE)
        try:
            token = f"{self.session_key}@{self.server}:{self.port}"
            with open(OMERO_CREDENTIAL_FILE, 'w') as token_file:
                token_file.write(token)
            LOGGER.debug(f"Made temp token for {self.server}")
        except:
            LOGGER.error("Unable to write temporary token", exc_info=True)

    def try_temp_token(self):
        # Look for and attempt to connect to OMERO using a temporary token.
        if not os.path.exists(OMERO_CREDENTIAL_FILE):
            LOGGER.error(f"No temporary OMERO token found. Cannot connect to server.")
            return False
        with open(OMERO_CREDENTIAL_FILE, 'r') as token_path:
            token = token_path.read().strip()
        server, port = token[token.find('@') + 1:].split(':')
        port = int(port)
        session_key = token[:token.find('@')]
        LOGGER.info(f"Using connection details for {self.server}")
        return self.login(server=server, port=port, session_key=session_key)

    def login(self, server=None, port=None, user=None, passwd=None, session_key=None):
        # Attempt to connect to the server using provided connection credentials
        self.client = omero.client(host=server, port=port)
        if session_key is not None:
            try:
                self.session = self.client.joinSession(session_key)
                self.client.enableKeepAlive(60)
                self.session.detachOnDestroy()
                self.server = server
                self.port = port
                self.session_key = session_key
            except Exception as e:
                LOGGER.error(f"Failed to join session, token may have expired: {e}")
                self.client = None
                self.session = None
                return False
        elif self.username is not None:
            try:
                self.session = self.client.createSession(
                    username=user, password=passwd)
                self.client.enableKeepAlive(60)
                self.session.detachOnDestroy()
                self.session_key = self.client.getSessionId()
                self.server = server
                self.port = port
                self.username = user
                self.passwd = passwd
            except Exception as e:
                LOGGER.error(f"Failed to create session: {e}")
                self.client = None
                self.session = None
                return False
        else:
            self.client = None
            self.session = None
            raise Exception(
                "Not enough details to create a server connection.")
        self.container_service = self.session.getContainerService()
        return True

    def shutdown(self):
        # Disconnect from the server
        if self.client is not None:
            try:
                self.client.closeSession()
            except Exception as e:
                LOGGER.error("Failed to close OMERO session - ", e)


CREDENTIALS = LoginHelper()
