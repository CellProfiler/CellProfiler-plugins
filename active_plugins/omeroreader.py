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
import os
import collections
import atexit

from struct import unpack

from cellprofiler_core.preferences import get_headless

import numpy

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

PASSTHROUGH_SCHEMES.append('OMERO')

SCALE_ONE_TYPE = ["float", "double"]
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
    Reads images from OMERO.
    """
    reader_name = "OMERO Reader"
    variable_revision_number = 1
    supported_filetypes = {}
    supported_schemes = {'omero', 'http', 'https'}

    def __init__(self, image_file):
        self.login = CREDENTIALS
        self.image_id = None
        self.omero_image = None
        self.pixels = None
        self.width = None
        self.height = None
        self.context = {'omero.group': '-1'}
        super().__init__(image_file)

    def __del__(self):
        self.close()

    def confirm_connection(self):
        if self.login.client is None:
            if get_headless():
                raise ValueError("No OMERO connection established")
            else:
                login(None)
                if self.login.client is None:
                    raise ValueError("Connection failed")

    def init_reader(self):
        # Check if session object already exists
        self.confirm_connection()
        if self.omero_image is not None:
            return True
        if self.file.scheme == "omero":
            self.image_id = int(self.file.url[10:])
        else:
            matches = REGEX_INDEX_FROM_FILE_NAME.findall(self.file.url)
            if not matches:
                raise ValueError("URL may not be from OMERO")
            self.image_id = int(matches[0])

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
        """
        self.init_reader()

        debug_message = \
            "Reading C: %s, Z: %s, T: %s, series: %s, index: %s, " \
            "channel names: %s, rescale: %s, wants_max_intensity: %s, " \
            "XYWH: %s" % (c, z, t, series, index, channel_names, rescale,
                          wants_max_intensity, xywh)
        if c is None and index is not None:
            c = index
        LOGGER.info(debug_message)
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
        numpy_image = self.read_planes(z, c, t, tile)
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
        self.init_reader()
        debug_message = \
            "Reading C: %s, Z: %s, T: %s, series: %s, index: %s, " \
            "channel names: %s, rescale: %s, wants_max_intensity: %s, " \
            "XYWH: %s" % (c, z, t, series, index, channel_names, rescale,
                          wants_max_intensity, xywh)
        if c is None and index is not None:
            c = index
        LOGGER.info(debug_message)
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
            # consitent with the CellProfiler reader (the double type is also
            # converted to single precision)
            numpy_image = \
                (numpy_image.astype(numpy.float32) + float(min_value)) / \
                (float(max_value) - float(min_value))
        if wants_max_intensity:
            return numpy_image, max_value
        return numpy_image

    def read_planes(self, z=0, c=None, t=0, tile=None):
        '''
        Creates RawPixelsStore and reads planes from the OMERO server.
        '''
        channels = []
        if c is None:
            channels = range(self.pixels.getSizeC().val)
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
        return True

    @classmethod
    def supports_format(cls, image_file, allow_open=False, volume=False):
        """This function needs to evaluate whether a given ImageFile object
        can be read by this reader class.

        Return value should be an integer representing suitability:
        -1 - 'I can't read this at all'
        1 - 'I am the one true reader for this format, don't even bother checking any others'
        2 - 'I am well-suited to this format'
        3 - 'I can read this format, but I might not be the best',
        4 - 'I can give it a go, if you must'

        The allow_open parameter dictates whether the reader is permitted to read the file when
        making this decision. If False the decision should be made using file extension only.
        Any opened files should be closed before returning.

        The volume parameter specifies whether the reader will need to return a 3D array.
        ."""
        if image_file.scheme not in cls.supported_schemes:
            return -1
        if image_file.scheme == "omero":
            return 1
        elif "?show=image" in image_file.url.lower():
            return 2
        return -1

    def close(self):
        # If your reader opens a file, this needs to release any active lock,
        pass

    def get_series_metadata(self):
        """
        OMERO image IDs only ever refer to a single series

        Should return a dictionary with the following keys:
        Key names are in cellprofiler_core.constants.image
        MD_SIZE_S - int reflecting the number of series
        MD_SIZE_X - list of X dimension sizes, one element per series.
        MD_SIZE_Y - list of Y dimension sizes, one element per series.
        MD_SIZE_Z - list of Z dimension sizes, one element per series.
        MD_SIZE_C - list of C dimension sizes, one element per series.
        MD_SIZE_T - list of T dimension sizes, one element per series.
        MD_SERIES_NAME - list of series names, one element per series.
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


def set_display_server(val):
    config_write_typed(key, value, key_type=bool)


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
        atexit.register(self.shutdown)
        
    def get_tokens(self, path=None):
        self.tokens.clear()
        # Future versions of omero_user_token may support multiple tokens, so we code with that in mind.
        if not TOKENS_AVAILABLE:
            return
        # User tokens sadly default to the home directory. This would override that location.
        py_home = os.environ['HOME']
        if path is not None:
            os.environ['HOME'] = path
        try:
            LOGGER.info("Requesting token info")
            token = omero_user_token.getter()
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
                print(f"Failed to join session, token may have expired: {e}")
                self.client = None
                self.session = None
                return False
        elif self.username is not None:
            try:
                self.session = self.client.createSession(
                    username=user, password=passwd)
                self.client.enableKeepAlive(60)
                self.session.detachOnDestroy()
                self.server = server
                self.port = port
                self.username = user
                self.passwd = passwd
            except Exception as e:
                print(f"Failed to create session: {e}")
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
                print("Failed to close OMERO session - ", e)


CREDENTIALS = LoginHelper()

if not get_headless():
    # We can only construct wx widgets if we're not in headless mode
    import wx
    import cellprofiler.gui.plugins_menu


    def show_login_dlg(token=True):
        app = wx.GetApp()
        frame = app.GetTopWindow()
        with OmeroLoginDlg(frame, title="Log into Omero", token=token) as dlg:
            dlg.ShowModal()

    def login(e):
        CREDENTIALS.get_tokens()
        if CREDENTIALS.tokens:
            connected = CREDENTIALS.try_token(list(CREDENTIALS.tokens.keys())[0])
            if get_headless():
                if connected:
                    print("Connected to ", CREDENTIALS.server)
                else:
                    print("Failed to connect, was user token invalid?")
                return connected
            elif connected:
                from cellprofiler.gui.errordialog import show_warning
                cellprofiler.gui.errordialog.show_warning("Connected to OMERO", 
                                                          f"A token was found and used to "
                                                          f"connect to the OMERO server at {CREDENTIALS.server}",
                                                          get_display_server, 
                                                          set_display_server)
                return
        show_login_dlg()

    def login_no_token(e):
        show_login_dlg()

    # def browse(e):
    #     if CREDENTIALS.client is None:
    #         show_login_dlg()
    #     browse_images()


    cellprofiler.gui.plugins_menu.PLUGIN_MENU_ENTRIES.extend([
        (login, wx.NewId(), "Connect to OMERO", "Establish an OMERO connection"),
        (login_no_token, wx.NewId(), "Connect to OMERO (no token)", "Establish an OMERO connection,"
                                                                    " but without using user tokens"),
        # (browse, wx.NewID(), "Browse OMERO for images", "Browse an OMERO server and add images to the pipeline")
    ])

    class OmeroLoginDlg(wx.Dialog):

        def __init__(self, *args, token=True, **kwargs):
            super(self.__class__, self).__init__(*args, **kwargs)
            self.credentials = CREDENTIALS
            self.token = token
            self.SetSizer(wx.BoxSizer(wx.VERTICAL))
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
            self.omero_server_ctrl = wx.TextCtrl(self, value=self.credentials.server)
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
                    print("Cancelled")
                    return
            token = omero_user_token.setter(
                self.cretentials.server,
                self.credentials.port,
                self.credentials.username,
                self.credentials.passwd,
                -1)
            if token:
                print("Done")
                self.message_ctrl.Label = "Connected. Token Set!"
                self.message_ctrl.ForegroundColour = "forest green"
            else:
                print("Failed")
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

# TODO: Connection manager
# TODO: user token support
# TODO: headless mode
# TODO: Handle multichannel images when requesting grey
