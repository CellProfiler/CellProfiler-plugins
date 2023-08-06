"""
An image reader which connects to OMERO to load data

# Installation -
Easy mode - clone the plugins repository and point your CellProfiler plugins folder to this folder.
Navigate to /active_plugins/ and run `pip install -e .[omero]` to install dependencies.

## Manual Installation

Add this file plus the `omero_helper` directory into your CellProfiler plugins folder. Install dependencies into
your CellProfiler Python environment.

## Installing dependencies -
This depends on platform. At the most basic level you'll need the `omero-py` package and the `omero_user_token` package.

Both should be possible to pip install on Windows. On MacOS, you'll probably have trouble with the zeroc-ice dependency.
omero-py uses an older version and so needs specific wheels. Fortunately we've built some for you.
Macos - https://github.com/glencoesoftware/zeroc-ice-py-macos-x86_64/releases/latest
Linux (Generic) - https://github.com/glencoesoftware/zeroc-ice-py-linux-x86_64/releases/latest
Ubuntu 22.04 - https://github.com/glencoesoftware/zeroc-ice-py-ubuntu2204-x86_64/releases/latest

Download the .whl file from whichever is most appropriate and run `pip install </path/to/my.whl>`.

From there pip install omero-py should do the rest.

You'll probably also want the `omero_user_token` package to help manage logins (`pip install omero_user_token`).
This allows you to set reusable login tokens for quick reconnection to a server. These tokens are required for using
headless mode.


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

In the Plugins menu you'll also find an option to browse an OMERO server for images and add them to your file list.
This provides an alternative method for constructing your file list. Images will be added to the list in the
OMERO URL format.

# Tokens -
omero_user_token creates a long-lasting session token based on your login credentials, which can then be reconnected to
at a later time. The CellProfiler plugin will detect and use these tokens to connect to a server automatically. Use the
`Connect to OMERO (No token)` option in the Plugins menu if you need to switch servers.

Within the connect dialog you'll find a new 'Set Token' button which allows you to create these tokens after making a
successful connection. These tokens are important when working in headless mode, but also mean that you no longer
need to enter your credentials each time you login via the GUI. Current omero_user_token builds support a single token
at a time, which will be stored in your user home directory.

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
import collections
import urllib.parse

from struct import unpack

import numpy

from cellprofiler_core.preferences import get_headless
from cellprofiler_core.constants.image import MD_SIZE_S, MD_SIZE_C, MD_SIZE_Z, MD_SIZE_T, \
    MD_SIZE_Y, MD_SIZE_X, MD_SERIES_NAME
from cellprofiler_core.constants.image import PASSTHROUGH_SCHEMES
from cellprofiler_core.reader import Reader

import logging
import re

from omero_helper.connect import login, CREDENTIALS

if not get_headless():
    # Load the GUI components and add the plugin menu options
    from omero_helper.gui import inject_plugin_menu_entries
    inject_plugin_menu_entries()

# Isolates image numbers from OMERO URLs
REGEX_INDEX_FROM_FILE_NAME = re.compile(r'\?show=image-(\d+)')

# Inject omero as a URI scheme which CellProfiler should accept as an image entry.
PASSTHROUGH_SCHEMES.append('omero')

LOGGER = logging.getLogger(__name__)

# Maps OMERO pixel types to numpy
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
    reader_name = "OMERO"
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
        """
        Creates RawPixelsStore and reads planes from the OMERO server.
        """
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
        """
        Creates RawPixelsStore and reads planes from the OMERO server.
        """
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
            # Looks enough like an OMERO URL that we'll have a go.
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
