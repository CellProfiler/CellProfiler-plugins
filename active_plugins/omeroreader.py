"""
An image reader which connects to OMERO to load data

# Installation -
This depends on platform. At the most basic level you'll need the `omero-py` package. For headless run and
more convenient server login you'll also want the `omero_user_token` package.

Both should be possible to pip install on Windows. On MacOS, you'll probably have trouble with the zeroc-ice dependency.
omero-py uses an older version and so needs specific wheels. Fortunately we've built some for you.
Macos - https://github.com/glencoesoftware/zeroc-ice-py-macos-x86_64/releases/latest
Linux (Generic) - https://github.com/glencoesoftware/zeroc-ice-py-linux-x86_64/releases/latest
Ubuntu 22.04 - https://github.com/glencoesoftware/zeroc-ice-py-ubuntu2204-x86_64/releases/latest

Download the .whl file from whichever is most appropriate and run `pip install </path/to/my.whl>`.

From there pip install omero-py should do the rest.

# Usage -
Like the old functionality from <=CP4, connection to OMERO is triggered through a login dialog within the GUI which
should appear automatically when needed. Enter your credentials and hit 'connect'. Once connected you should be able to
load OMERO data into the workspace.

We've also made a "Connect to OMERO" menu option available in the new Plugins menu, in case you ever need to forcibly
open that window again (e.g. changing server).

To get OMERO data into a pipeline, you can construct a file list in the special URL format `omero:iid=<image_id>`.
E.g. "omero:iid=4345"

Alternatively, direct URLs pointing to an image can be provided.
e.g. https://omero.mywebsite.com/webclient/?show=image-1234
These can be obtained in OMERO-web by selecting an image and pressing the link button in the top right corner
of the right side panel.

To get these into the CellProfiler GUI, there are a few options. Previously this was primarily achieved by using
*File->Import->File List* to load a text file containing one image per line. A LoadData CSV can also be used.
As of CP5 it is also now possible to copy and paste text (e.g. URLs) directly into the file list in the Images module.

# Working with data -
Unlike previous iterations of this integration, the CP5 plugin has full support for channel and plane indexing.
The previous reader misbehaved in that it would only load the first channel from OMERO if greyscale is requested.
In this version all channels will be returned, so you must declare a colour image in NamesAndTypes when loading one.

On the plus side, you can now use the 'Extract metadata' option in the Images module to split the C, Z and T axes
into individual planes. Remember to disable the "Filter to images only" option in the Images module, since URLs do
not pass this filter.

Lastly, with regards to connections, you can only connect to a single server at a time. Opening the connect dialog and
dialling in will replace any existing connection which you had active. This iteration of the plugin will keep
server connections from timing out while CellProfiler is running, though you may need to reconnect if the PC
goes to sleep.
"""
import base64
import functools
import io
import os
import collections
import atexit
from io import BytesIO
import requests
import urllib.parse

from struct import unpack

import numpy

from cellprofiler_core.preferences import get_headless
from cellprofiler_core.constants.image import MD_SIZE_S, MD_SIZE_C, MD_SIZE_Z, MD_SIZE_T, \
    MD_SIZE_Y, MD_SIZE_X, MD_SERIES_NAME
from cellprofiler_core.preferences import get_omero_server, get_omero_port, get_omero_user, set_omero_server,\
    set_omero_port, set_omero_user, config_read_typed, config_write_typed
from cellprofiler_core.constants.image import PASSTHROUGH_SCHEMES
from cellprofiler_core.reader import Reader

import omero
import logging
import re

import importlib.util

TOKEN_MODULE = importlib.util.find_spec("omero_user_token")
TOKENS_AVAILABLE = TOKEN_MODULE is not None
if TOKENS_AVAILABLE:
    # Only load and enable user tokens if dependency is installed
    omero_user_token = importlib.util.module_from_spec(TOKEN_MODULE)
    TOKEN_MODULE.loader.exec_module(omero_user_token)


REGEX_INDEX_FROM_FILE_NAME = re.compile(r'\?show=image-(\d+)')

# Inject omero as a URI scheme which CellProfiler should accept as an image entry.
PASSTHROUGH_SCHEMES.append('omero')

LOGGER = logging.getLogger(__name__)

PIXEL_TYPES = {
        "int8": ['b', numpy.int8, (-128, 127)],
        "uint8": ['B', numpy.uint8, (0, 255)],
        "int16": ['h', numpy.int16, (-32768, 32767)],
        "uint16": ['H', numpy.uint16, (0, 65535)],
        "int32": ['i', numpy.int32, (-2147483648, 2147483647)],
        "uint32": ['I', numpy.uint32, (0, 4294967295)],
        "float": ['f', numpy.float32, (0, 1)],
        "double": ['d', numpy.float64, (0, 1)]
}


class OMEROReader(Reader):
    """
    Reads images from an OMERO server.
    """
    reader_name = "OMERO Reader"
    variable_revision_number = 1
    supported_filetypes = {}
    supported_schemes = {'omero', 'http', 'https'}

    def __init__(self, image_file):
        self.login = CREDENTIALS
        self.image_id = None
        self.server = None
        self.omero_image = None
        self.pixels = None
        self.width = None
        self.height = None
        self.context = {'omero.group': '-1'}
        super().__init__(image_file)

    def __del__(self):
        self.close()

    def confirm_connection(self):
        # Verify that we're able to connect to a server
        if self.login.client is None:
            if get_headless():
                connected = login(server=self.server)
                if connected:
                    return True
                else:
                    raise ValueError("No OMERO connection established")
            else:
                login(server=self.server)
                if self.login.client is None:
                    raise ValueError("Connection failed")

    def init_reader(self):
        # Setup the reader
        if self.omero_image is not None:
            # We're already connected and have fetched the image pointer
            return True
        if self.file.scheme == "omero":
            self.image_id = int(self.file.url[10:])
        else:
            matches = REGEX_INDEX_FROM_FILE_NAME.findall(self.file.url)
            if not matches:
                raise ValueError("URL may not be from OMERO?")
            self.image_id = int(matches[0])
            self.server = urllib.parse.urlparse(self.file.url).hostname

        # Check if session object already exists
        self.confirm_connection()

        LOGGER.debug("Initializing OmeroReader for Image id: %s" % self.image_id)
        # Get image object from the server
        try:
            self.omero_image = self.login.container_service.getImages(
                "Image", [self.image_id], None, self.context)[0]
        except:
            message = "Image Id: %s not found on the server." % self.image_id
            LOGGER.error(message, exc_info=True)
            raise Exception(message)
        self.pixels = self.omero_image.getPrimaryPixels()
        self.width = self.pixels.getSizeX().val
        self.height = self.pixels.getSizeY().val
        return True

    def read(self,
             series=None,
             index=None,
             c=None,
             z=None,
             t=None,
             rescale=True,
             xywh=None,
             wants_max_intensity=False,
             channel_names=None,
             volumetric=False,
             ):
        """Read a single plane from the image file.
        :param c: read from this channel. `None` = read color image if multichannel
            or interleaved RGB.
        :param z: z-stack index
        :param t: time index
        :param series: series for ``.flex`` and similar multi-stack formats
        :param index: if `None`, fall back to ``zct``, otherwise load the indexed frame
        :param rescale: `True` to rescale the intensity scale to 0 and 1; `False` to
                  return the raw values native to the file.
        :param xywh: a (x, y, w, h) tuple
        :param wants_max_intensity: if `False`, only return the image; if `True`,
                  return a tuple of image and max intensity
        :param channel_names: provide the channel names for the OME metadata
        :param volumetric: Whether we're reading in 3D
        """
        self.init_reader()
        debug_message = \
            "Reading C: %s, Z: %s, T: %s, series: %s, index: %s, " \
            "channel names: %s, rescale: %s, wants_max_intensity: %s, " \
            "XYWH: %s" % (c, z, t, series, index, channel_names, rescale,
                          wants_max_intensity, xywh)
        if c is None and index is not None:
            c = index
        LOGGER.debug(debug_message)
        message = None
        if (t or 0) >= self.pixels.getSizeT().val:
            message = "T index %s exceeds sizeT %s" % \
                      (t, self.pixels.getSizeT().val)
            LOGGER.error(message)
        if (c or 0) >= self.pixels.getSizeC().val:
            message = "C index %s exceeds sizeC %s" % \
                      (c, self.pixels.getSizeC().val)
            LOGGER.error(message)
        if (z or 0) >= self.pixels.getSizeZ().val:
            message = "Z index %s exceeds sizeZ %s" % \
                      (z, self.pixels.getSizeZ().val)
            LOGGER.error(message)
        if message is not None:
            raise Exception("Couldn't retrieve a plane from OMERO image.")
        tile = None
        if xywh is not None:
            assert isinstance(xywh, tuple) and len(xywh) == 4, \
                "Invalid XYWH tuple"
            tile = xywh
        if not volumetric:
            numpy_image = self.read_planes(z, c, t, tile)
        else:
            numpy_image = self.read_planes_volumetric(z, c, t, tile)
        pixel_type = self.pixels.getPixelsType().value.val
        min_value = PIXEL_TYPES[pixel_type][2][0]
        max_value = PIXEL_TYPES[pixel_type][2][1]
        LOGGER.debug("Pixel range [%s, %s]" % (min_value, max_value))
        if rescale or pixel_type == 'double':
            LOGGER.info("Rescaling image using [%s, %s]" % (min_value, max_value))
            # Note: The result here differs from:
            #     https://github.com/emilroz/python-bioformats/blob/a60b5c5a5ae018510dd8aa32d53c35083956ae74/bioformats/formatreader.py#L903
            # Reason: the unsigned types are being properly taken into account
            # and converted to [0, 1] using their full scale.
            # Further note: float64 should be used for the numpy array in case
            # image is stored as 'double', we're keeping it float32 to stay
            # consistent with the CellProfiler reader (the double type is also
            # converted to single precision)
            numpy_image = \
                (numpy_image.astype(numpy.float32) + float(min_value)) / \
                (float(max_value) - float(min_value))
        if wants_max_intensity:
            return numpy_image, max_value
        return numpy_image

    def read_volume(self,
                    series=None,
                    c=None,
                    z=None,
                    t=None,
                    rescale=True,
                    xywh=None,
                    wants_max_intensity=False,
                    channel_names=None,
                    ):
        # Forward 3D calls to the standard reader function
        return self.read(
            series=series,
            c=c,
            z=z,
            t=t,
            rescale=rescale,
            xywh=xywh,
            wants_max_intensity=wants_max_intensity,
            channel_names=channel_names,
            volumetric=True
        )

    def read_planes(self, z=0, c=None, t=0, tile=None):
        '''
        Creates RawPixelsStore and reads planes from the OMERO server.
        '''
        channels = []
        if c is None:
            channel_count = self.pixels.getSizeC().val
            if channel_count == 1:
                # This is obviously greyscale, treat it as such.
                channels.append(0)
                c = 0
            else:
                channels = range(channel_count)
        else:
            channels.append(c)
        pixel_type = self.pixels.getPixelsType().value.val
        numpy_type = PIXEL_TYPES[pixel_type][1]
        raw_pixels_store = self.login.session.createRawPixelsStore()
        try:
            raw_pixels_store.setPixelsId(
                self.pixels.getId().val, True, self.context)
            LOGGER.debug("Reading pixels Id: %s" % self.pixels.getId().val)
            LOGGER.debug("Reading channels %s" % channels)
            planes = []
            for channel in channels:
                if tile is None:
                    sizeX = self.width
                    sizeY = self.height
                    raw_plane = raw_pixels_store.getPlane(
                        z, channel, t, self.context)
                else:
                    x, y, sizeX, sizeY = tile
                    raw_plane = raw_pixels_store.getTile(
                        z, channel, t, x, y, sizeX, sizeY)
                convert_type = '>%d%s' % (
                    (sizeY * sizeX), PIXEL_TYPES[pixel_type][0])
                converted_plane = unpack(convert_type, raw_plane)
                plane = numpy.array(converted_plane, numpy_type)
                plane.resize(sizeY, sizeX)
                planes.append(plane)
            if c is None:
                return numpy.dstack(planes)
            else:
                return planes[0]
        except Exception:
            LOGGER.error("Failed to get plane from OMERO", exc_info=True)
        finally:
            raw_pixels_store.close()

    def read_planes_volumetric(self, z=None, c=None, t=None, tile=None):
        '''
        Creates RawPixelsStore and reads planes from the OMERO server.
        '''
        if t is not None and z is not None:
            raise ValueError(f"Specified parameters {z=}, {t=} would not produce a 3D image")
        if z is None:
            size_z = self.pixels.getSizeZ().val
        else:
            size_z = 1
        if t is None:
            size_t = self.pixels.getSizeT().val
        else:
            size_t = 1
        pixel_type = self.pixels.getPixelsType().value.val
        numpy_type = PIXEL_TYPES[pixel_type][1]
        raw_pixels_store = self.login.session.createRawPixelsStore()
        if size_z > 1:
            # We assume z is the desired 3D dimension if present and not specified.
            t_range = [t or 0]
            z_range = range(size_z)
        elif size_t > 1:
            t_range = range(size_t)
            z_range = [z or 0]
        else:
            # Weird, but perhaps user's 3D image only had 1 plane in this acquisition.
            t_range = [t or 0]
            z_range = [z or 0]
        planes = []
        try:
            raw_pixels_store.setPixelsId(
                self.pixels.getId().val, True, self.context)
            LOGGER.debug("Reading pixels Id: %s" % self.pixels.getId().val)

            for z_index in z_range:
                for t_index in t_range:
                    if tile is None:
                        size_x = self.width
                        size_y = self.height
                        raw_plane = raw_pixels_store.getPlane(
                            z_index, c, t_index, self.context)
                    else:
                        x, y, size_x, size_y = tile
                        raw_plane = raw_pixels_store.getTile(
                            z_index, c, t_index, x, y, size_x, size_y)
                    convert_type = '>%d%s' % (
                        (size_y * size_x), PIXEL_TYPES[pixel_type][0])
                    converted_plane = unpack(convert_type, raw_plane)
                    plane = numpy.array(converted_plane, numpy_type)
                    plane.resize(size_y, size_x)
                    planes.append(plane)
            return numpy.dstack(planes)
        except Exception:
            LOGGER.error("Failed to get plane from OMERO", exc_info=True)
        finally:
            raw_pixels_store.close()

    @classmethod
    def supports_url(cls):
        # We read OMERO URLs directly without caching a download.
        return True

    @classmethod
    def supports_format(cls, image_file, allow_open=False, volume=False):
        if image_file.scheme not in cls.supported_schemes:
            # I can't read this
            return -1
        if image_file.scheme == "omero":
            # Yes please
            return 1
        elif "?show=image" in image_file.url.lower():
            # Looks enough like an OMERO URL that I'll have a go.
            return 2
        return -1

    def close(self):
        # We don't activate any file locks.
        pass

    def get_series_metadata(self):
        """
        OMERO image IDs only ever refer to a single series
        """
        self.init_reader()
        LOGGER.info(f"Extracting metadata for image {self.image_id}")
        meta_dict = collections.defaultdict(list)
        meta_dict[MD_SIZE_S] = 1
        meta_dict[MD_SIZE_X].append(self.width)
        meta_dict[MD_SIZE_Y].append(self.height)
        meta_dict[MD_SIZE_C].append(self.pixels.getSizeC().val)
        meta_dict[MD_SIZE_Z].append(self.pixels.getSizeZ().val)
        meta_dict[MD_SIZE_T].append(self.pixels.getSizeT().val)
        meta_dict[MD_SERIES_NAME].append(self.omero_image.getName().val)
        return meta_dict

    @staticmethod
    def get_settings():
        # Define settings available in the reader
        return [
            ('allow_token',
             "Allow OMERO user tokens",
             """
             If enabled, this reader will attempt to use OMERO user tokens to
             establish a server connection.
             """,
             bool,
             True),
            ('show_server',
             "Display 'server connected' popup",
             """
             If enabled, a popup will be shown when a server is automatically connected to using a user token.
             """,
             bool,
             True)
        ]


def get_display_server():
    return config_read_typed(f"Reader.{OMEROReader.reader_name}.show_server", bool)


def set_display_server(value):
    config_write_typed(f"Reader.{OMEROReader.reader_name}.show_server", value, key_type=bool)


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
        tokens_enabled = config_read_typed(f"Reader.{OMEROReader.reader_name}.allow_token", bool)
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
                client.closeSession()
            except Exception as e:
                LOGGER.error("Failed to close OMERO session - ", e)


CREDENTIALS = LoginHelper()

if not get_headless():
    # We can only construct wx widgets if we're not in headless mode
    import wx
    import cellprofiler.gui.plugins_menu


    def show_login_dlg(token=True, server=None):
        app = wx.GetApp()
        frame = app.GetTopWindow()
        with OmeroLoginDlg(frame, title="Log into Omero", token=token, server=server) as dlg:
            dlg.ShowModal()

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
            elif connected:
                from cellprofiler.gui.errordialog import show_warning
                show_warning("Connected to OMERO",
                             f"A token was found and used to connect to the OMERO server at {CREDENTIALS.server}",
                             get_display_server,
                             set_display_server)
                return
        show_login_dlg(server=server)

    def login_no_token(e):
        show_login_dlg()


    def browse(e):
        if CREDENTIALS.client is None:
            login()
        app = wx.GetApp()
        frame = app.GetTopWindow()
        if CREDENTIALS.browser_window is None:
            CREDENTIALS.browser_window = OmeroBrowseDlg(frame, title=f"Browse OMERO: {CREDENTIALS.server}")
            CREDENTIALS.browser_window.Show()
        else:
            CREDENTIALS.browser_window.Raise()


    cellprofiler.gui.plugins_menu.PLUGIN_MENU_ENTRIES.extend([
        (login, wx.NewId(), "Connect to OMERO", "Establish an OMERO connection"),
        (login_no_token, wx.NewId(), "Connect to OMERO (no token)", "Establish an OMERO connection,"
                                                                    " but without using user tokens"),
        (browse, wx.NewId(), "Browse OMERO for images", "Browse an OMERO server and add images to the pipeline")
    ])

    class OmeroLoginDlg(wx.Dialog):

        def __init__(self, *args, token=True, server=None, **kwargs):
            super(self.__class__, self).__init__(*args, **kwargs)
            self.credentials = CREDENTIALS
            self.token = token
            self.SetSizer(wx.BoxSizer(wx.VERTICAL))
            if server is None:
                server = self.credentials.server
            sizer = wx.BoxSizer(wx.VERTICAL)
            self.Sizer.Add(sizer, 1, wx.EXPAND | wx.ALL, 6)
            sub_sizer = wx.BoxSizer(wx.HORIZONTAL)
            sizer.Add(sub_sizer, 0, wx.EXPAND)
    
            max_width = 0
            max_height = 0
            for label in ("Server:", "Port:", "Username:", "Password:"):
                w, h, _, _ = self.GetFullTextExtent(label)
                max_width = max(w, max_width)
                max_height = max(h, max_height)
    
            # Add extra padding
            lsize = wx.Size(max_width + 5, max_height)
            sub_sizer.Add(
                wx.StaticText(self, label="Server:", size=lsize),
                0, wx.ALIGN_CENTER_VERTICAL)
            self.omero_server_ctrl = wx.TextCtrl(self, value=server)
            sub_sizer.Add(self.omero_server_ctrl, 1, wx.EXPAND)
    
            sizer.AddSpacer(5)
            sub_sizer = wx.BoxSizer(wx.HORIZONTAL)
            sizer.Add(sub_sizer, 0, wx.EXPAND)
            sub_sizer.Add(
                wx.StaticText(self, label="Port:", size=lsize),
                0, wx.ALIGN_CENTER_VERTICAL)
            self.omero_port_ctrl = wx.lib.intctrl.IntCtrl(self, value=self.credentials.port)
            sub_sizer.Add(self.omero_port_ctrl, 1, wx.EXPAND)
    
            sizer.AddSpacer(5)
            sub_sizer = wx.BoxSizer(wx.HORIZONTAL)
            sizer.Add(sub_sizer, 0, wx.EXPAND)
            sub_sizer.Add(
                wx.StaticText(self, label="User:", size=lsize),
                0, wx.ALIGN_CENTER_VERTICAL)
            self.omero_user_ctrl = wx.TextCtrl(self, value=self.credentials.username)
            sub_sizer.Add(self.omero_user_ctrl, 1, wx.EXPAND)
    
            sizer.AddSpacer(5)
            sub_sizer = wx.BoxSizer(wx.HORIZONTAL)
            sizer.Add(sub_sizer, 0, wx.EXPAND)
            sub_sizer.Add(
                wx.StaticText(self, label="Password:", size=lsize),
                0, wx.ALIGN_CENTER_VERTICAL)
            self.omero_password_ctrl = wx.TextCtrl(self, value="", style=wx.TE_PASSWORD|wx.TE_PROCESS_ENTER)
            self.omero_password_ctrl.Bind(wx.EVT_TEXT_ENTER, self.on_connect_pressed)
            if self.credentials.username is not None:
                self.omero_password_ctrl.SetFocus()
            sub_sizer.Add(self.omero_password_ctrl, 1, wx.EXPAND)
    
            sizer.AddSpacer(5)
            sub_sizer = wx.BoxSizer(wx.HORIZONTAL)
            sizer.Add(sub_sizer, 0, wx.EXPAND)
            connect_button = wx.Button(self, label="Connect")
            connect_button.Bind(wx.EVT_BUTTON, self.on_connect_pressed)
            sub_sizer.Add(connect_button, 0, wx.EXPAND)
            sub_sizer.AddSpacer(5)
    
            self.message_ctrl = wx.StaticText(self, label="Not connected")
            sub_sizer.Add(self.message_ctrl, 1, wx.EXPAND)

            self.token_button = wx.Button(self, label="Set Token")
            self.token_button.Bind(wx.EVT_BUTTON, self.on_set_pressed)
            self.token_button.Disable()
            self.token_button.SetToolTip("Use these credentials to set a long-lasting token for automatic login")
            sub_sizer.Add(self.token_button, 0, wx.EXPAND)
            sub_sizer.AddSpacer(5)

    
            button_sizer = wx.StdDialogButtonSizer()
            self.Sizer.Add(button_sizer, 0, wx.EXPAND)
    
            cancel_button = wx.Button(self, wx.ID_CANCEL)
            button_sizer.AddButton(cancel_button)
            cancel_button.Bind(wx.EVT_BUTTON, self.on_cancel)
    
            self.ok_button = wx.Button(self, wx.ID_OK)
            button_sizer.AddButton(self.ok_button)
            self.ok_button.Bind(wx.EVT_BUTTON, self.on_ok)
            self.ok_button.Enable(False)
            button_sizer.Realize()
    
            self.omero_password_ctrl.Bind(wx.EVT_TEXT, self.mark_dirty)
            self.omero_port_ctrl.Bind(wx.EVT_TEXT, self.mark_dirty)
            self.omero_server_ctrl.Bind(wx.EVT_TEXT, self.mark_dirty)
            self.omero_user_ctrl.Bind(wx.EVT_TEXT, self.mark_dirty)
            self.Layout()
    
        def mark_dirty(self, event):
            if self.ok_button.IsEnabled():
                self.ok_button.Enable(False)
                self.message_ctrl.Label = "Please connect with your new credentials"
                self.message_ctrl.ForegroundColour = "black"
    
        def on_connect_pressed(self, event):
            if self.credentials.client is not None and self.credentials.server == self.omero_server_ctrl.GetValue():
                # Already connected, accept another 'Connect' command as an ok to close
                self.EndModal(wx.OK)
            self.connect()

        def on_set_pressed(self, event):
            if self.credentials.client is None or not TOKENS_AVAILABLE:
                return
            token_path = omero_user_token.assert_and_get_token_path()
            if os.path.exists(token_path):
                dlg2 = wx.MessageDialog(self,
                                        "Existing omero_user_token will be overwritten. Proceed?",
                                        "Overwrite existing token?",
                                        wx.YES_NO | wx.CANCEL | wx.ICON_WARNING)
                result = dlg2.ShowModal()
                if result != wx.ID_YES:
                    LOGGER.debug("Cancelled")
                    return
            token = omero_user_token.setter(
                self.credentials.server,
                self.credentials.port,
                self.credentials.username,
                self.credentials.passwd,
                -1)
            if token:
                LOGGER.info("Set OMERO user token")
                self.message_ctrl.Label = "Connected. Token Set!"
                self.message_ctrl.ForegroundColour = "forest green"
            else:
                LOGGER.error("Failed to set OMERO user token")
                self.message_ctrl.Label = "Failed to set token."
                self.message_ctrl.ForegroundColour = "red"
            self.message_ctrl.Refresh()

        def connect(self):
            try:
                server = self.omero_server_ctrl.GetValue()
                port = self.omero_port_ctrl.GetValue()
                user = self.omero_user_ctrl.GetValue()
                passwd = self.omero_password_ctrl.GetValue()
            except:
                self.message_ctrl.Label = (
                    "The port number must be an integer between 0 and 65535 (try 4064)"
                )
                self.message_ctrl.ForegroundColour = "red"
                self.message_ctrl.Refresh()
                return False
            self.message_ctrl.ForegroundColour = "black"
            self.message_ctrl.Label = "Connecting..."
            self.message_ctrl.Refresh()
            # Allow UI to update before connecting
            wx.Yield()
            success = self.credentials.login(server, port, user, passwd)
            if success:
                self.message_ctrl.Label = "Connected"
                self.message_ctrl.ForegroundColour = "forest green"
                self.token_button.Enable()
                self.message_ctrl.Refresh()
                set_omero_server(server)
                set_omero_port(port)
                set_omero_user(user)
                self.ok_button.Enable(True)
                return True
            else:
                self.message_ctrl.Label = "Failed to log onto server"
                self.message_ctrl.ForegroundColour = "red"
                self.message_ctrl.Refresh()
                self.token_button.Disable()
                return False
    
        def on_cancel(self, event):
            self.EndModal(wx.CANCEL)
    
        def on_ok(self, event):
            self.EndModal(wx.OK)


    class OmeroBrowseDlg(wx.Frame):
        def __init__(self, *args, **kwargs):
            super(self.__class__, self).__init__(*args,
                                                 style=wx.RESIZE_BORDER | wx.CAPTION | wx.CLOSE_BOX,
                                                 size=(800, 600),
                                                 **kwargs)
            self.credentials = CREDENTIALS
            self.admin_service = self.credentials.session.getAdminService()
            self.url_loader = self.Parent.pipeline.add_urls

            self.Bind(wx.EVT_CLOSE, self.close_browser)

            ec = self.admin_service.getEventContext()
            # Exclude sys groups
            self.groups = [self.admin_service.getGroup(v) for v in ec.memberOfGroups if v > 1]
            self.group_names = [group.name.val for group in self.groups]
            self.current_group = self.groups[0].id.getValue()
            self.users_in_group = {'All Members': -1}
            self.users_in_group.update({
                x.omeName.val: x.id.val for x in self.groups[0].linkedExperimenterList()
            })
            self.current_user = -1
            self.levels = {'projects': 'datasets',
                           'datasets': 'images',
                           'screens': 'plates',
                           'orphaned': 'images'
                           }

            splitter = wx.SplitterWindow(self, -1, style=wx.SP_BORDER)
            self.browse_controls = wx.Panel(splitter, -1)
            b = wx.BoxSizer(wx.VERTICAL)

            self.groups_box = wx.Choice(self.browse_controls, choices=self.group_names)
            self.groups_box.Bind(wx.EVT_CHOICE, self.switch_group)

            self.members_box = wx.Choice(self.browse_controls, choices=list(self.users_in_group.keys()))
            self.members_box.Bind(wx.EVT_CHOICE, self.switch_member)

            b.Add(self.groups_box, 0, wx.EXPAND)
            b.Add(self.members_box, 0, wx.EXPAND)
            self.container = self.credentials.session.getContainerService()

            self.tree = wx.TreeCtrl(self.browse_controls, style=wx.TR_HAS_BUTTONS | wx.TR_HIDE_ROOT)
            image_list = wx.ImageList(16, 12)
            image_data = {
                'projects': 'iVBORw0KGgoAAAANSUhEUgAAABAAAAANCAYAAACgu+4kAAAAGXRFWHRTb2Z0d2FyZQBBZG9iZSBJbWFnZVJlYWR5ccllPAAAA5NpVFh0WE1MOmNvbS5hZG9iZS54bXAAAAAAADw/eHBhY2tldCBiZWdpbj0i77u/IiBpZD0iVzVNME1wQ2VoaUh6cmVTek5UY3prYzlkIj8+IDx4OnhtcG1ldGEgeG1sbnM6eD0iYWRvYmU6bnM6bWV0YS8iIHg6eG1wdGs9IkFkb2JlIFhNUCBDb3JlIDUuMy1jMDExIDY2LjE0NTY2MSwgMjAxMi8wMi8wNi0xNDo1NjoyNyAgICAgICAgIj4gPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4gPHJkZjpEZXNjcmlwdGlvbiByZGY6YWJvdXQ9IiIgeG1sbnM6eG1wTU09Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC9tbS8iIHhtbG5zOnN0UmVmPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvc1R5cGUvUmVzb3VyY2VSZWYjIiB4bWxuczp4bXA9Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC8iIHhtcE1NOk9yaWdpbmFsRG9jdW1lbnRJRD0ieG1wLmRpZDpDNDk5ODU0N0U5MjA2ODExODhDNkJBNzRDM0U2QkE2NyIgeG1wTU06RG9jdW1lbnRJRD0ieG1wLmRpZDpFNjZDNDcxNzc5NEUxMUUxOTY2OEJEQjhGOUExQ0Y3RCIgeG1wTU06SW5zdGFuY2VJRD0ieG1wLmlpZDpFNjZDNDcxNjc5NEUxMUUxOTY2OEJEQjhGOUExQ0Y3RCIgeG1wOkNyZWF0b3JUb29sPSJBZG9iZSBQaG90b3Nob3AgQ1M2ICgxMy4wIDIwMTIwMzA1Lm0uNDE1IDIwMTIvMDMvMDU6MjE6MDA6MDApICAoTWFjaW50b3NoKSI+IDx4bXBNTTpEZXJpdmVkRnJvbSBzdFJlZjppbnN0YW5jZUlEPSJ4bXAuaWlkOkM1NzAxRDEzMjkyMTY4MTE4OEM2QkE3NEMzRTZCQTY3IiBzdFJlZjpkb2N1bWVudElEPSJ4bXAuZGlkOkM0OTk4NTQ3RTkyMDY4MTE4OEM2QkE3NEMzRTZCQTY3Ii8+IDwvcmRmOkRlc2NyaXB0aW9uPiA8L3JkZjpSREY+IDwveDp4bXBtZXRhPiA8P3hwYWNrZXQgZW5kPSJyIj8+vd9MhwAAALhJREFUeNpi/P//P0NEXsd/BhxgxaQKRgY8gAXGMNbVwpA8e/kaAyHAGJhWe5iNnctGVkoaQ/Lxs6cMv35+w6f/CMvfP39svDytscrqaijgtX3t5u02IAMYXrx5z0AOAOll+fPnF8Ov37/IMgCkl+XP799Af5JpAFAv0IBfDD9//STTAKALfgMJcl0A0gvxwi8KvPAXFIhkGvAXHIjAqPjx4zuZsQCMxn9//my9eOaEFQN54ChAgAEAzRBnWnEZWFQAAAAASUVORK5CYII=',
                'datasets': 'iVBORw0KGgoAAAANSUhEUgAAABAAAAANCAYAAACgu+4kAAAAGXRFWHRTb2Z0d2FyZQBBZG9iZSBJbWFnZVJlYWR5ccllPAAAA5NpVFh0WE1MOmNvbS5hZG9iZS54bXAAAAAAADw/eHBhY2tldCBiZWdpbj0i77u/IiBpZD0iVzVNME1wQ2VoaUh6cmVTek5UY3prYzlkIj8+IDx4OnhtcG1ldGEgeG1sbnM6eD0iYWRvYmU6bnM6bWV0YS8iIHg6eG1wdGs9IkFkb2JlIFhNUCBDb3JlIDUuMy1jMDExIDY2LjE0NTY2MSwgMjAxMi8wMi8wNi0xNDo1NjoyNyAgICAgICAgIj4gPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4gPHJkZjpEZXNjcmlwdGlvbiByZGY6YWJvdXQ9IiIgeG1sbnM6eG1wTU09Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC9tbS8iIHhtbG5zOnN0UmVmPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvc1R5cGUvUmVzb3VyY2VSZWYjIiB4bWxuczp4bXA9Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC8iIHhtcE1NOk9yaWdpbmFsRG9jdW1lbnRJRD0ieG1wLmRpZDpDNDk5ODU0N0U5MjA2ODExODhDNkJBNzRDM0U2QkE2NyIgeG1wTU06RG9jdW1lbnRJRD0ieG1wLmRpZDpFNjZGMDA2ODc5NEUxMUUxOTY2OEJEQjhGOUExQ0Y3RCIgeG1wTU06SW5zdGFuY2VJRD0ieG1wLmlpZDpFNjZDNDcxQTc5NEUxMUUxOTY2OEJEQjhGOUExQ0Y3RCIgeG1wOkNyZWF0b3JUb29sPSJBZG9iZSBQaG90b3Nob3AgQ1M2ICgxMy4wIDIwMTIwMzA1Lm0uNDE1IDIwMTIvMDMvMDU6MjE6MDA6MDApICAoTWFjaW50b3NoKSI+IDx4bXBNTTpEZXJpdmVkRnJvbSBzdFJlZjppbnN0YW5jZUlEPSJ4bXAuaWlkOkM1NzAxRDEzMjkyMTY4MTE4OEM2QkE3NEMzRTZCQTY3IiBzdFJlZjpkb2N1bWVudElEPSJ4bXAuZGlkOkM0OTk4NTQ3RTkyMDY4MTE4OEM2QkE3NEMzRTZCQTY3Ii8+IDwvcmRmOkRlc2NyaXB0aW9uPiA8L3JkZjpSREY+IDwveDp4bXBtZXRhPiA8P3hwYWNrZXQgZW5kPSJyIj8+l9tKdwAAAKZJREFUeNpi/P//P0NUm+d/BhxgWdV2RgY8gAXGMNMwwpA8deMcAyHAEljsdJhTmJ3h1YfnWBUA5f/j0X+E5d+//zYhrv5YZU108du+cNlKG6AB/xjefn7FQA4A6WX59/cfw5/ff8gz4C/IAKApf/78pswFv3/9Jt8Ff8FeIM+AvzAv/KbUC/8oC8T/DN9//iLTBf8ZWP7/+7f18MELVgzkgaMAAQYAgLlmT8qQW/sAAAAASUVORK5CYII=',
                'screens': 'iVBORw0KGgoAAAANSUhEUgAAABEAAAANCAYAAABPeYUaAAAAGXRFWHRTb2Z0d2FyZQBBZG9iZSBJbWFnZVJlYWR5ccllPAAAA5NpVFh0WE1MOmNvbS5hZG9iZS54bXAAAAAAADw/eHBhY2tldCBiZWdpbj0i77u/IiBpZD0iVzVNME1wQ2VoaUh6cmVTek5UY3prYzlkIj8+IDx4OnhtcG1ldGEgeG1sbnM6eD0iYWRvYmU6bnM6bWV0YS8iIHg6eG1wdGs9IkFkb2JlIFhNUCBDb3JlIDUuMy1jMDExIDY2LjE0NTY2MSwgMjAxMi8wMi8wNi0xNDo1NjoyNyAgICAgICAgIj4gPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4gPHJkZjpEZXNjcmlwdGlvbiByZGY6YWJvdXQ9IiIgeG1sbnM6eG1wTU09Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC9tbS8iIHhtbG5zOnN0UmVmPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvc1R5cGUvUmVzb3VyY2VSZWYjIiB4bWxuczp4bXA9Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC8iIHhtcE1NOk9yaWdpbmFsRG9jdW1lbnRJRD0ieG1wLmRpZDpDNDk5ODU0N0U5MjA2ODExODhDNkJBNzRDM0U2QkE2NyIgeG1wTU06RG9jdW1lbnRJRD0ieG1wLmRpZDo5NkU0QUUzNjc4NEExMUUxOTY2OEJEQjhGOUExQ0Y3RCIgeG1wTU06SW5zdGFuY2VJRD0ieG1wLmlpZDo5NkU0QUUzNTc4NEExMUUxOTY2OEJEQjhGOUExQ0Y3RCIgeG1wOkNyZWF0b3JUb29sPSJBZG9iZSBQaG90b3Nob3AgQ1M2ICgxMy4wIDIwMTIwMzA1Lm0uNDE1IDIwMTIvMDMvMDU6MjE6MDA6MDApICAoTWFjaW50b3NoKSI+IDx4bXBNTTpEZXJpdmVkRnJvbSBzdFJlZjppbnN0YW5jZUlEPSJ4bXAuaWlkOkM1NzAxRDEzMjkyMTY4MTE4OEM2QkE3NEMzRTZCQTY3IiBzdFJlZjpkb2N1bWVudElEPSJ4bXAuZGlkOkM0OTk4NTQ3RTkyMDY4MTE4OEM2QkE3NEMzRTZCQTY3Ii8+IDwvcmRmOkRlc2NyaXB0aW9uPiA8L3JkZjpSREY+IDwveDp4bXBtZXRhPiA8P3hwYWNrZXQgZW5kPSJyIj8+wkwZRwAAAQxJREFUeNpi/P//PwMjIyODqbHhfwYc4PTZ84y45ED6WZAFPFxdwQYig+27djEQAowgk6wtLcGu4GBnY0C38vvPX3gNOHr8OCPcJaHh4QwsLCwYiv78+YNV87+/fxnWrlkDZsN1PXr0iGHPnj1wRS4uLnj5jg4OcDYTjPH7928w3WxmhcJ3zmtC4Zc2mUH4SC6EG/LrF8TvtaeOofD3TqpD4XfXnULho3gHJOjt7Q2XePHiBV7+s6dPsRuydetWuISuri5evra2Nm7vVKUZoPDTratR+EZV1RjewTCkbdYFFP7Mo60o/HNtrSgBjeEdMzMzuMRToJ/x8Z88eYJpyKcPH8AYGRDiwwBAgAEAvXKdXsBF6t8AAAAASUVORK5CYII='
            }
            self.image_codes = {}
            for name, dat in image_data.items():
                decodedImgData = base64.b64decode(dat)
                bio = BytesIO(decodedImgData)
                img = wx.Image(bio)
                self.image_codes[name] = image_list.Add(img.ConvertToBitmap())
            self.tree.AssignImageList(image_list)

            self.tree.Bind(wx.EVT_TREE_ITEM_EXPANDING, self.fetch_children)
            self.tree.Bind(wx.EVT_TREE_SEL_CHANGING, self.select_tree)
            self.tree.Bind(wx.EVT_TREE_SEL_CHANGED, self.update_thumbnails)
            self.tree.Bind(wx.EVT_TREE_BEGIN_DRAG, self.process_drag)

            data = self.fetch_containers()

            self.populate_tree(data)
            b.Add(self.tree, 1, wx.EXPAND)

            self.browse_controls.SetSizer(b)

            self.image_controls = wx.Panel(splitter, -1)

            vert_sizer = wx.BoxSizer(wx.VERTICAL)

            self.tile_panel = wx.ScrolledWindow(self.image_controls, 1)
            self.tile_panel.url_loader = self.url_loader

            self.tiler_sizer = wx.WrapSizer(wx.HORIZONTAL)
            self.tile_panel.SetSizer(self.tiler_sizer)
            self.tile_panel.SetScrollbars(0, 20, 0, 20)

            self.update_thumbnails()
            vert_sizer.Add(self.tile_panel, wx.EXPAND)

            add_button = wx.Button(self.image_controls, wx.NewId(), "Add to file list")
            add_button.Bind(wx.EVT_BUTTON, self.add_selected_to_pipeline)
            vert_sizer.Add(add_button, 0, wx.ALIGN_RIGHT | wx.ALL, 5)
            self.image_controls.SetSizer(vert_sizer)
            splitter.SplitVertically(self.browse_controls, self.image_controls, 200)

            self.Layout()

        def close_browser(self, event):
            self.credentials.browser_window = None
            event.Skip()

        def add_selected_to_pipeline(self, e=None):
            displayed = self.tile_panel.GetChildren()
            all_urls = []
            selected_urls = []
            for item in displayed:
                if isinstance(item, ImagePanel):
                    all_urls.append(item.url)
                    if item.selected:
                        selected_urls.append(item.url)
            if selected_urls:
                self.url_loader(selected_urls)
            else:
                self.url_loader(all_urls)

        def process_drag(self, event):
            # We have our own custom handler here
            data = wx.FileDataObject()
            for file_url in self.fetch_file_list_from_tree(event):
                data.AddFile(file_url)
            drop_src = wx.DropSource(self)
            drop_src.SetData(data)
            drop_src.DoDragDrop(wx.Drag_CopyOnly)

        def fetch_file_list_from_tree(self, event):
            files = []

            def recurse_for_images(tree_id):
                if not self.tree.IsExpanded(tree_id):
                    self.tree.Expand(tree_id)
                data = self.tree.GetItemData(tree_id)
                item_type = data['type']
                if item_type == 'images':
                    files.append(f"https://{self.credentials.server}/webclient/?show=image-{data['id']}")
                elif 'images' in data:
                    for omero_id, _ in data['images'].items():
                        files.append(f"https://{self.credentials.server}/webclient/?show=image-{omero_id}")
                else:
                    child_id, cookie = self.tree.GetFirstChild(tree_id)
                    while child_id.IsOk():
                        recurse_for_images(child_id)
                        child_id, cookie = self.tree.GetNextChild(tree_id, cookie)

            recurse_for_images(event.GetItem())
            return files

        def select_tree(self, event):
            target_id = event.GetItem()
            self.tree.Expand(target_id)

        def next_level(self, level):
            return self.levels.get(level, None)

        def switch_group(self, e=None):
            new_group = self.groups_box.GetCurrentSelection()
            self.current_group = self.groups[new_group].id.getValue()
            self.current_user = -1
            self.refresh_group_members()
            data = self.fetch_containers()
            self.populate_tree(data)

        def switch_member(self, e=None):
            new_member = self.members_box.GetStringSelection()
            self.current_user = self.users_in_group.get(new_member, -1)
            data = self.fetch_containers()
            self.populate_tree(data)

        def refresh_group_members(self):
            self.users_in_group = {'All Members': -1}
            group = self.groups[self.groups_box.GetCurrentSelection()]
            self.users_in_group.update({
                x.omeName.val: x.id.val for x in group.linkedExperimenterList()
            })
            self.members_box.Clear()
            self.members_box.AppendItems(list(self.users_in_group.keys()))


        def fetch_children(self, event):
            target_id = event.GetItem()
            data = self.tree.GetItemData(target_id)
            self.tree.DeleteChildren(target_id)
            subject_type = data['type']
            target_type = self.levels.get(subject_type, None)
            if target_type is None:
                # We're at the bottom level already
                return
            subject = data['id']
            if subject == -1:
                sub_str = "orphaned=true&"
            else:
                sub_str = f"id={subject}&"
            url = f"https://{self.credentials.server}/webclient/api/{target_type}/?{sub_str}experimenter_id=-1&page=0&group={self.current_group}&bsession={self.credentials.session_key}"

            try:
                result = requests.get(url, timeout=5)
            except requests.exceptions.ConnectTimeout:
                LOGGER.error("Server request timed out")
                return
            result.raise_for_status()
            result = result.json()
            if 'images' in result:
                image_map = {entry['id']: entry['name'] for entry in result['images']}
                data['images'] = image_map
                self.tree.SetItemData(target_id, data)
            self.populate_tree(result, target_id)

        def fetch_containers(self):
            url = f"https://{self.credentials.server}/webclient/api/containers/?id={self.current_user}&page=0&group={self.current_group}&bsession={self.credentials.session_key}"
            try:
                data = requests.get(url, timeout=5)
            except requests.exceptions.ConnectTimeout:
                LOGGER.error("Server request timed out")
                return {}
            data.raise_for_status()
            return data.json()

        def fetch_thumbnails(self, id_list):
            if not id_list:
                return {}
            id_list = [str(x) for x in id_list]
            chunk_size = 10
            buffer = {x: "" for x in id_list}
            for i in range(0, len(id_list), chunk_size):
                ids_to_get = '&id='.join(id_list[i:i + chunk_size])
                url = f"https://{self.credentials.server}/webclient/get_thumbnails/128/?&bsession={self.credentials.session_key}&id={ids_to_get}"
                LOGGER.debug(f"Fetching {url}")
                try:
                    data = requests.get(url, timeout=5)
                except requests.exceptions.ConnectTimeout:
                    continue
                if data.status_code != 200:
                    LOGGER.warning(f"Server error: {data.status_code} - {data.reason}")
                else:
                    buffer.update(data.json())
            return buffer

        @functools.lru_cache(maxsize=20)
        def fetch_large_thumbnail(self, id):
            # Get a large thumbnail for single image display mode. We cache the last 20.
            url = f"https://{self.credentials.server}/webgateway/render_thumbnail/{id}/450/450/?bsession={self.credentials.session_key}"
            LOGGER.debug(f"Fetching {url}")
            try:
                data = requests.get(url, timeout=5)
            except requests.exceptions.ConnectTimeout:
                LOGGER.error("Thumbnail request timed out")
                return False
            if data.status_code != 200:
                LOGGER.warning("Server error:", data.status_code, data.reason)
                return False
            elif not data.content:
                return False
            io_bytes = io.BytesIO(data.content)
            return wx.Image(io_bytes)

        def update_thumbnails(self, event=None):
            self.tiler_sizer.Clear(delete_windows=True)
            if not event:
                return
            target_id = event.GetItem()
            item_data = self.tree.GetItemData(target_id)
            if item_data.get('type', None) == 'images':
                image_id = item_data['id']
                img_name = item_data['name']
                thumb_img = self.fetch_large_thumbnail(image_id)
                if not thumb_img or not thumb_img.IsOk():
                    thumb_img = self.get_error_thumbnail(450)
                else:
                    thumb_img = thumb_img.ConvertToBitmap()
                tile = ImagePanel(thumb_img, self.tile_panel, image_id, img_name, self.credentials.server, size=450)
                tile.selected = True
                self.tiler_sizer.Add(tile, 0, wx.ALL, 5)
            else:
                image_targets = item_data.get('images', {})
                if not image_targets:
                    return

                id_list = list(image_targets.keys())
                data = self.fetch_thumbnails(id_list)
                for image_id, image_data in data.items():
                    img_name = image_targets[int(image_id)]
                    start_data = image_data.find('/9')
                    if start_data == -1:
                        img = self.get_error_thumbnail(128)
                    else:
                        decoded = base64.b64decode(image_data[start_data:])
                        bio = BytesIO(decoded)
                        img = wx.Image(bio)
                        if not img.IsOk():
                            img = self.get_error_thumbnail(128)
                        else:
                            img = img.ConvertToBitmap()
                    tile = ImagePanel(img, self.tile_panel, image_id, img_name, self.credentials.server)
                    self.tiler_sizer.Add(tile, 0, wx.ALL, 5)
            self.tiler_sizer.Layout()
            self.image_controls.Layout()
            self.image_controls.Refresh()

        @functools.lru_cache(maxsize=10)
        def get_error_thumbnail(self, size):
            # Draw an image with an error icon. Cache the result since we may need the error icon repeatedly.
            artist = wx.ArtProvider()
            size //= 2
            return artist.GetBitmap(wx.ART_WARNING, size=(size, size))

        def populate_tree(self, data, parent=None):
            if parent is None:
                self.tree.DeleteAllItems()
                parent = self.tree.AddRoot("Server")
            for item_type, items in data.items():
                image = self.image_codes.get(item_type, None)
                if not isinstance(items, list):
                    items = [items]
                for entry in items:
                    entry['type'] = item_type
                    new_id = self.tree.AppendItem(parent, f"{entry['name']}", data=entry)
                    if image is not None:
                        self.tree.SetItemImage(new_id, image, wx.TreeItemIcon_Normal)
                    if entry.get('childCount', 0) > 0:
                        self.tree.SetItemHasChildren(new_id)


    class ImagePanel(wx.Panel):
        '''
        ImagePanels are wxPanels that display a wxBitmap and store multiple
        image channels which can be recombined to mix different bitmaps.
        '''

        def __init__(self, thumbnail, parent, omero_id, name, server, size=128):
            """
            thumbnail -- wx Bitmap
            parent -- parent window to the wx.Panel

            """
            self.parent = parent
            self.bitmap = thumbnail
            self.selected = False
            self.omero_id = omero_id
            self.url = f"https://{server}/webclient/?show=image-{omero_id}"
            self.name = name
            if len(name) > 17:
                self.shortname = name[:14] + '...'
            else:
                self.shortname = name
            self.size_x = size
            self.size_y = size + 30
            wx.Panel.__init__(self, parent, wx.NewId(), size=(self.size_x, self.size_y))
            self.Bind(wx.EVT_PAINT, self.OnPaint)
            self.Bind(wx.EVT_LEFT_DOWN, self.select)
            self.Bind(wx.EVT_RIGHT_DOWN, self.right_click)
            self.SetClientSize((self.size_x, self.size_y))

        def select(self, e):
            self.selected = not self.selected
            self.Refresh()
            e.StopPropagation()
            e.Skip()

        def right_click(self, event):
            popupmenu = wx.Menu()
            add_file_item = popupmenu.Append(-1, "Add to file list")
            self.Bind(wx.EVT_MENU, self.add_to_pipeline, add_file_item)
            add_file_item = popupmenu.Append(-1, "Show in OMERO.web")
            self.Bind(wx.EVT_MENU, self.open_in_browser, add_file_item)
            # Show menu
            self.PopupMenu(popupmenu, event.GetPosition())

        def add_to_pipeline(self, e):
            self.parent.url_loader([self.url])

        def open_in_browser(self, e):
            wx.LaunchDefaultBrowser(self.url)

        def OnPaint(self, evt):
            dc = wx.PaintDC(self)
            dc.Clear()
            dc.DrawBitmap(self.bitmap, (self.size_x - self.bitmap.Width) // 2,
                          ((self.size_x - self.bitmap.Height) // 2) + 20)
            rect = wx.Rect(0, 0, self.size_x, self.size_x + 20)
            dc.DrawLabel(self.shortname, rect, alignment=wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_TOP)
            dc.SetPen(wx.Pen("GREY", style=wx.PENSTYLE_SOLID))
            dc.SetBrush(wx.Brush("BLACK", wx.TRANSPARENT))
            dc.DrawRectangle(rect)
            # Outline the whole image
            if self.selected:
                dc.SetPen(wx.Pen("BLUE", 3))
                dc.SetBrush(wx.Brush("BLACK", style=wx.TRANSPARENT))
                dc.DrawRectangle(0, 0, self.size_x, self.size_y)
            return dc

# Todo: Make better drag selection
# Todo: Split GUI into a helper module
# Todo: Handle wells/fields
