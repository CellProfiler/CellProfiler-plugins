import atexit
import os
import logging
import importlib.util

from cellprofiler_core.preferences import config_read_typed, get_headless
from cellprofiler_core.preferences import get_omero_server, get_omero_port, get_omero_user
import omero

LOGGER = logging.getLogger(__name__)

TOKEN_MODULE = importlib.util.find_spec("omero_user_token")
TOKENS_AVAILABLE = TOKEN_MODULE is not None
if TOKENS_AVAILABLE:
    # Only load and enable user tokens if dependency is installed
    omero_user_token = importlib.util.module_from_spec(TOKEN_MODULE)
    TOKEN_MODULE.loader.exec_module(omero_user_token)


def login(e=None, server=None):
    CREDENTIALS.get_tokens()
    if CREDENTIALS.tokens:
        if server is None:
            # URL didn't specify which server we want. Just try whichever token is available
            server = list(CREDENTIALS.tokens.keys())[0]
        connected = CREDENTIALS.try_token(server)
        if get_headless():
            if connected:
                LOGGER.info("Connected to ", CREDENTIALS.server)
            else:
                LOGGER.warning("Failed to connect, was user token invalid?")
            return connected
        else:
            from .gui import login_gui
            login_gui(connected, server=None)


class LoginHelper:
    def __init__(self):
        self.server = get_omero_server()
        self.port = get_omero_port()
        self.username = get_omero_user()
        self.passwd = ""
        self.session_key = None
        self.session = None
        self.client = None
        self.container_service = None
        self.tokens = {}
        self.browser_window = None
        atexit.register(self.shutdown)

    def get_tokens(self, path=None):
        self.tokens.clear()
        # Future versions of omero_user_token may support multiple tokens, so we code with that in mind.
        if not TOKENS_AVAILABLE:
            return
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
        if address not in self.tokens:
            LOGGER.error(f"Token {address} not found")
            return False
        else:
            server, port, session_key = self.tokens[address]
            return self.login(server=server, port=port, session_key=session_key)

    def login(self, server=None, port=None, user=None, passwd=None, session_key=None):
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
        if self.client is not None:
            try:
                self.client.closeSession()
            except Exception as e:
                LOGGER.error("Failed to close OMERO session - ", e)


CREDENTIALS = LoginHelper()
