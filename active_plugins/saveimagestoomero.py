"""
SaveImagesToOMERO
==================

**SaveImagesToOMERO**  saves image or movies directly onto an
OMERO server.

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

You'll also want the `omero_user_token` package to help manage logins (`pip install omero_user_token`).
This allows you to set reusable login tokens for quick reconnection to a server. These tokens are required for using
headless mode/analysis mode.

|

============ ============ ===============
Supports 2D? Supports 3D? Respects masks?
============ ============ ===============
YES          YES          YES
============ ============ ===============

"""

import logging
import os

import numpy
import skimage
from cellprofiler_core.module import Module
from cellprofiler_core.preferences import get_headless
from cellprofiler_core.setting import Binary
from cellprofiler_core.setting import ValidationError
from cellprofiler_core.setting.choice import Choice
from cellprofiler_core.setting.do_something import DoSomething
from cellprofiler_core.setting.subscriber import ImageSubscriber, FileImageSubscriber
from cellprofiler_core.setting.text import Integer, Text
from cellprofiler_core.constants.setting import get_name_providers

from cellprofiler.modules import _help

from omero_helper.connect import CREDENTIALS, login

LOGGER = logging.getLogger(__name__)

FN_FROM_IMAGE = "From image filename"
FN_SEQUENTIAL = "Sequential numbers"
FN_SINGLE_NAME = "Single name"

SINGLE_NAME_TEXT = "Enter single file name"
SEQUENTIAL_NUMBER_TEXT = "Enter file prefix"

BIT_DEPTH_8 = "8-bit integer"
BIT_DEPTH_16 = "16-bit integer"
BIT_DEPTH_FLOAT = "32-bit floating point"
BIT_DEPTH_RAW = "No conversion"

WS_EVERY_CYCLE = "Every cycle"
WS_FIRST_CYCLE = "First cycle"
WS_LAST_CYCLE = "Last cycle"


class SaveImagesToOMERO(Module):
    module_name = "SaveImagesToOMERO"
    variable_revision_number = 1
    category = ["File Processing"]

    def create_settings(self):
        self.target_object_id = Integer(
            text="OMERO ID of the parent dataset",
            minval=1,
            doc="""\
        The created images must be added to an OMERO dataset.
        Enter the OMERO ID of the Dataset object you'd like to associate 
        the the image with. This ID can be found by locating the target object
        in OMERO.web (ID and type is displayed in the right panel).
        
        To use a new dataset, first create this in OMERO.web and then enter the ID here""",
        )

        self.test_connection_button = DoSomething(
            "Test the OMERO connection",
            "Test connection",
            self.test_connection,
            doc="""\
This button test the connection to the OMERO server specified using
the settings entered by the user.""",
        )

        self.image_name = ImageSubscriber(
            "Select the image to save", doc="Select the image you want to save."
        )

        self.bit_depth = Choice(
            "Image bit depth conversion",
            [BIT_DEPTH_8, BIT_DEPTH_16, BIT_DEPTH_FLOAT, BIT_DEPTH_RAW],
            BIT_DEPTH_RAW,
            doc=f"""\
        Select the bit-depth at which you want to save the images. CellProfiler 
        typically works with images scaled into the 0-1 range. This setting lets 
        you transform that into other scales.
        
        Selecting *{BIT_DEPTH_RAW}* will attempt to upload data without applying 
        any transformations. This could be used to save integer labels 
        in 32-bit float format if you had more labels than the 16-bit format can 
        handle (without rescaling to the 0-1 range of *{BIT_DEPTH_FLOAT}*). 
        N.B. data compatibility with OMERO is not checked.
        
        *{BIT_DEPTH_8}* and *{BIT_DEPTH_16}* will attempt to rescale values to 
        be in the range 0-255 and 0-65535 respectively. These are typically 
        used with external tools.
        
        *{BIT_DEPTH_FLOAT}* saves the image as floating-point decimals with
        32-bit precision. When the input data is integer or binary type, pixel
        values are scaled within the range (0, 1). Floating point data is not
        rescaled.""",
        )

        self.file_name_method = Choice(
            "Select method for constructing file names",
            [FN_FROM_IMAGE, FN_SEQUENTIAL, FN_SINGLE_NAME],
            FN_FROM_IMAGE,
            doc="""\
        *(Used only if saving non-movie files)*

        Several choices are available for constructing the image file name:

        -  *{FN_FROM_IMAGE}:* The filename will be constructed based on the
           original filename of an input image specified in **NamesAndTypes**.
           You will have the opportunity to prefix or append additional text.

           If you have metadata associated with your images, you can append
           text to the image filename using a metadata tag. This is especially
           useful if you want your output given a unique label according to the
           metadata corresponding to an image group. The name of the metadata to
           substitute can be provided for each image for each cycle using the
           **Metadata** module.
        -  *{FN_SEQUENTIAL}:* Same as above, but in addition, each filename
           will have a number appended to the end that corresponds to the image
           cycle number (starting at 1).
        -  *{FN_SINGLE_NAME}:* A single name will be given to the file. Since
           the filename is fixed, this file will be overwritten with each cycle.
           In this case, you would probably want to save the image on the last
           cycle (see the *Select how often to save* setting). The exception to
           this is to use a metadata tag to provide a unique label, as mentioned
           in the *{FN_FROM_IMAGE}* option.

        {USING_METADATA_TAGS_REF}

        {USING_METADATA_HELP_REF}
        """.format(
                **{
                    "FN_FROM_IMAGE": FN_FROM_IMAGE,
                    "FN_SEQUENTIAL": FN_SEQUENTIAL,
                    "FN_SINGLE_NAME": FN_SINGLE_NAME,
                    "USING_METADATA_HELP_REF": _help.USING_METADATA_HELP_REF,
                    "USING_METADATA_TAGS_REF": _help.USING_METADATA_TAGS_REF,
                }
            ),
        )

        self.file_image_name = FileImageSubscriber(
            "Select image name for file prefix",
            "None",
            doc="""\
        *(Used only when “{FN_FROM_IMAGE}” is selected for constructing the filename)*

        Select an image loaded using **NamesAndTypes**. The original filename
        will be used as the prefix for the output filename.""".format(
                **{"FN_FROM_IMAGE": FN_FROM_IMAGE}
            ),
        )

        self.single_file_name = Text(
            SINGLE_NAME_TEXT,
            "OrigBlue",
            metadata=True,
            doc="""\
        *(Used only when “{FN_SEQUENTIAL}” or “{FN_SINGLE_NAME}” are selected
        for constructing the filename)*

        Specify the filename text here. If you have metadata associated with
        your images, enter the filename text with the metadata tags.
        {USING_METADATA_TAGS_REF}
        Do not enter the file extension in this setting; it will be appended
        automatically.""".format(
                **{
                    "FN_SEQUENTIAL": FN_SEQUENTIAL,
                    "FN_SINGLE_NAME": FN_SINGLE_NAME,
                    "USING_METADATA_TAGS_REF": _help.USING_METADATA_TAGS_REF,
                }
            ),
        )

        self.number_of_digits = Integer(
            "Number of digits",
            4,
            doc="""\
        *(Used only when “{FN_SEQUENTIAL}” is selected for constructing the filename)*

        Specify the number of digits to be used for the sequential numbering.
        Zeros will be used to left-pad the digits. If the number specified here
        is less than that needed to contain the number of image sets, the latter
        will override the value entered.""".format(
                **{"FN_SEQUENTIAL": FN_SEQUENTIAL}
            ),
        )

        self.wants_file_name_suffix = Binary(
            "Append a suffix to the image file name?",
            False,
            doc="""\
        Select "*{YES}*" to add a suffix to the image’s file name. Select "*{NO}*"
        to use the image name as-is.
                    """.format(
                **{"NO": "No", "YES": "Yes"}
            ),
        )

        self.file_name_suffix = Text(
            "Text to append to the image name",
            "",
            metadata=True,
            doc="""\
        *(Used only when constructing the filename from the image filename)*

        Enter the text that should be appended to the filename specified above.
        If you have metadata associated with your images, you may use metadata tags.

        {USING_METADATA_TAGS_REF}

        Do not enter the file extension in this setting; it will be appended
        automatically.
        """.format(
                **{"USING_METADATA_TAGS_REF": _help.USING_METADATA_TAGS_REF}
            ),
        )

        self.when_to_save = Choice(
            "When to save",
            [WS_EVERY_CYCLE, WS_FIRST_CYCLE, WS_LAST_CYCLE],
            WS_EVERY_CYCLE,
            doc="""\
        Specify at what point during pipeline execution to save file(s).

        -  *{WS_EVERY_CYCLE}:* Useful for when the image of interest is
           created every cycle and is not dependent on results from a prior
           cycle.
        -  *{WS_FIRST_CYCLE}:* Useful for when you are saving an aggregate
           image created on the first cycle, e.g.,
           **CorrectIlluminationCalculate** with the *All* setting used on
           images obtained directly from **NamesAndTypes**.
        -  *{WS_LAST_CYCLE}:* Useful for when you are saving an aggregate image
           completed on the last cycle, e.g., **CorrectIlluminationCalculate**
           with the *All* setting used on intermediate images generated during
           each cycle.""".format(
                **{
                    "WS_EVERY_CYCLE": WS_EVERY_CYCLE,
                    "WS_FIRST_CYCLE": WS_FIRST_CYCLE,
                    "WS_LAST_CYCLE": WS_LAST_CYCLE,
                }
            ),
        )

    def settings(self):
        result = [
            self.target_object_id,
            self.image_name,
            self.bit_depth,
            self.file_name_method,
            self.file_image_name,
            self.single_file_name,
            self.number_of_digits,
            self.wants_file_name_suffix,
            self.file_name_suffix,
            self.when_to_save,
        ]
        return result

    def visible_settings(self):
        result = [self.target_object_id, self.test_connection_button,
                  self.image_name, self.bit_depth, self.file_name_method]

        if self.file_name_method == FN_FROM_IMAGE:
            result += [self.file_image_name, self.wants_file_name_suffix]
            if self.wants_file_name_suffix:
                result.append(self.file_name_suffix)
        elif self.file_name_method == FN_SEQUENTIAL:
            self.single_file_name.text = SEQUENTIAL_NUMBER_TEXT
            result.append(self.single_file_name)
            result.append(self.number_of_digits)
        elif self.file_name_method == FN_SINGLE_NAME:
            self.single_file_name.text = SINGLE_NAME_TEXT
            result.append(self.single_file_name)
        else:
            raise NotImplementedError(
                "Unhandled file name method: %s" % self.file_name_method
            )
        result.append(self.when_to_save)
        return result

    def help_settings(self):
        return [
            self.target_object_id,
            self.image_name,
            self.bit_depth,
            self.file_name_method,
            self.file_image_name,
            self.single_file_name,
            self.number_of_digits,
            self.wants_file_name_suffix,
            self.file_name_suffix,
            self.when_to_save,
        ]

    def validate_module(self, pipeline):
        # Make sure metadata tags exist
        if self.file_name_method == FN_SINGLE_NAME or (
            self.file_name_method == FN_FROM_IMAGE and self.wants_file_name_suffix.value
        ):
            text_str = (
                self.single_file_name.value
                if self.file_name_method == FN_SINGLE_NAME
                else self.file_name_suffix.value
            )
            undefined_tags = pipeline.get_undefined_metadata_tags(text_str)
            if len(undefined_tags) > 0:
                raise ValidationError(
                    "%s is not a defined metadata tag. Check the metadata specifications in your load modules"
                    % undefined_tags[0],
                    self.single_file_name
                    if self.file_name_method == FN_SINGLE_NAME
                    else self.file_name_suffix,
                )
        if self.when_to_save in (WS_FIRST_CYCLE, WS_EVERY_CYCLE):
            #
            # Make sure that the image name is available on every cycle
            #
            for setting in get_name_providers(pipeline, self.image_name):
                if setting.provided_attributes.get("available_on_last"):
                    #
                    # If we fell through, then you can only save on the last cycle
                    #
                    raise ValidationError(
                        "%s is only available after processing all images in an image group"
                        % self.image_name.value,
                        self.when_to_save,
                    )

    def test_connection(self):
        """Check to make sure the OMERO server is remotely accessible"""
        # CREDENTIALS is a singleton so we can safely grab it here.
        if CREDENTIALS.client is None:
            login()
            if CREDENTIALS.client is None:
                msg = "OMERO connection failed"
            else:
                msg = f"Connected to {CREDENTIALS.server}"
        else:
            msg = f"Already connected to {CREDENTIALS.server}"
        if CREDENTIALS.client is not None:
            try:
                self.get_omero_parent()
                msg += f"\n\nFound parent object {self.target_object_id}"
            except ValueError as ve:
                msg += f"\n\n{ve}"

        import wx
        wx.MessageBox(msg)

    def make_full_filename(self, file_name, workspace=None, image_set_index=None):
        """Convert a file name into an absolute path

        We do a few things here:
        * apply metadata from an image set to the file name if an
          image set is specified
        * change the relative path into an absolute one using the "." and "&"
          convention
        * Create any directories along the path
        """
        if image_set_index is not None and workspace is not None:
            file_name = workspace.measurements.apply_metadata(
                file_name, image_set_index
            )
        measurements = None if workspace is None else workspace.measurements
        path_name = self.directory.get_absolute_path(measurements, image_set_index)
        file_name = os.path.join(path_name, file_name)
        path, file = os.path.split(file_name)
        if not os.path.isdir(path):
            os.makedirs(path)
        return os.path.join(path, file)

    @staticmethod
    def connect_to_omero():
        if CREDENTIALS.client is None:
            if get_headless():
                connected = login()
                if not connected:
                    raise ValueError("No OMERO connection established")
            else:
                login()
                if CREDENTIALS.client is None:
                    raise ValueError("OMERO connection failed")

    def prepare_run(self, workspace):
        """Prepare to run the pipeline.
        Establish a connection to OMERO."""
        pipeline = workspace.pipeline

        if pipeline.in_batch_mode():
            return True

        # Verify that we're able to connect to a server
        self.connect_to_omero()

        return True

    def get_omero_conn(self):
        self.connect_to_omero()
        return CREDENTIALS.get_gateway()

    def get_omero_parent(self):
        conn = self.get_omero_conn()
        parent_id = self.target_object_id.value
        parent_type = "Dataset"
        old_group = conn.SERVICE_OPTS.getOmeroGroup()
        # Search across groups
        conn.SERVICE_OPTS.setOmeroGroup(-1)
        parent_ob = conn.getObject(parent_type, parent_id)
        if parent_ob is None:
            raise ValueError(f"{parent_type} ID {parent_id} not found on server")
        conn.SERVICE_OPTS.setOmeroGroup(old_group)
        return parent_ob

    def run(self, workspace):
        if self.show_window:
            workspace.display_data.wrote_image = False

        if self.when_to_save == WS_FIRST_CYCLE and workspace.measurements["Image", "Group_Index", ] > 1:
            # We're past the first image set
            return
        elif self.when_to_save == WS_LAST_CYCLE:
            # We do this in post group
            return

        self.save_image(workspace)

    def save_image(self, workspace):
        # Re-establish server connection
        self.connect_to_omero()

        filename = self.get_filename(workspace)

        image = workspace.image_set.get_image(self.image_name.value)

        omero_image = self.upload_image_to_omero(image, filename)

        if self.show_window:
            workspace.display_data.wrote_image = True
            im_id = omero_image.getId()
            path = f"https://{CREDENTIALS.server}/webclient/?show=image-{im_id}"
            workspace.display_data.header = ["Image Name", "OMERO ID", "Server Location"]
            workspace.display_data.columns = [[filename, im_id, path]]

    def post_group(self, workspace, *args):
        if self.when_to_save == WS_LAST_CYCLE:
            self.save_image(workspace)

    def upload_image_to_omero(self, image, name):
        pixels = image.pixel_data.copy()
        volumetric = image.volumetric
        multichannel = image.multichannel

        if self.bit_depth.value == BIT_DEPTH_8:
            pixels = skimage.util.img_as_ubyte(pixels)
        elif self.bit_depth.value == BIT_DEPTH_16:
            pixels = skimage.util.img_as_uint(pixels)
        elif self.bit_depth.value == BIT_DEPTH_FLOAT:
            pixels = skimage.util.img_as_float32(pixels)
        elif self.bit_depth.value == BIT_DEPTH_RAW:
            # No bit depth transformation
            pass
        else:
            raise NotImplementedError(f"Unknown bit depth {self.bit_depth.value}")

        conn = self.get_omero_conn()
        parent = self.get_omero_parent()
        parent_group = parent.details.group.id.val
        old_group = conn.SERVICE_OPTS.getOmeroGroup()
        conn.SERVICE_OPTS.setOmeroGroup(parent_group)
        shape = pixels.shape
        if multichannel:
            size_c = shape[-1]
        else:
            size_c = 1
        if volumetric:
            size_z = shape[2]
        else:
            size_z = 1

        new_shape = list(shape)
        while len(new_shape) < 4:
            new_shape.append(1)
        upload_pixels = numpy.reshape(pixels, new_shape)

        def slice_iterator():
            for z in range(size_z):
                for c in range(size_c):
                    yield upload_pixels[:, :, z, c]

        # Upload the image data to OMERO
        LOGGER.debug("Transmitting data for image")
        omero_image = conn.createImageFromNumpySeq(
            slice_iterator(), name, size_z, size_c, 1, description="Image uploaded from CellProfiler",
            dataset=parent)
        LOGGER.debug("Transmission successful")
        conn.SERVICE_OPTS.setOmeroGroup(old_group)
        return omero_image

    def get_filename(self, workspace):
        """Concoct a filename for the current image based on the user settings"""
        measurements = workspace.measurements
        if self.file_name_method == FN_SINGLE_NAME:
            filename = self.single_file_name.value
            filename = workspace.measurements.apply_metadata(filename)
        elif self.file_name_method == FN_SEQUENTIAL:
            filename = self.single_file_name.value
            filename = workspace.measurements.apply_metadata(filename)
            n_image_sets = workspace.measurements.image_set_count
            ndigits = int(numpy.ceil(numpy.log10(n_image_sets + 1)))
            ndigits = max((ndigits, self.number_of_digits.value))
            padded_num_string = str(measurements.image_set_number).zfill(ndigits)
            filename = "%s%s" % (filename, padded_num_string)
        else:
            file_name_feature = self.source_file_name_feature
            filename = measurements.get_current_measurement("Image", file_name_feature)
            filename = os.path.splitext(filename)[0]
            if self.wants_file_name_suffix:
                suffix = self.file_name_suffix.value
                suffix = workspace.measurements.apply_metadata(suffix)
                filename += suffix
        return filename

    @property
    def source_file_name_feature(self):
        """The file name measurement for the exemplar disk image"""
        return "_".join(("FileName", self.file_image_name.value))

    def display(self, workspace, figure):
        if not workspace.display_data.columns:
            # Nothing to display
            return
        figure.set_subplots((1, 1))
        figure.subplot_table(
            0,
            0,
            workspace.display_data.columns,
            col_labels=workspace.display_data.header,
        )

    def display_post_run(self, workspace, figure):
        self.display(workspace, figure)

    def is_aggregation_module(self):
        """SaveImagesToOMERO is an aggregation module when it writes on the last cycle"""
        return (
            self.when_to_save == WS_LAST_CYCLE
        )

    def volumetric(self):
        return True
