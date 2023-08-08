"""
ExportToOMEROTable
==================

**ExportToOMEROTable** exports measurements directly into an
OMERO.table stored on an OMERO server.

An uploaded table is viewable in OMERO.web, it will be uploaded as an attachment to
an existing OMERO object.

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

# Limitations

- OMERO tables cannot have their columns changed after being initialised. For now,
this means that measurements cannot be added after the pipeline finishes (e.g. per-well averages).
For most use cases you can export all measurements produced by the pipeline, it'll be results from
complex modules like the LAP tracker in TrackObjects which cannot be fully exported.

- Groupings from the Groups module are currently not implemented. Everything goes into a single table.
This may be added in a future version, but for now a single table per image/object type is created
without support for splitting (much like ExportToDatabase).

- There is a limit to how much data can be transmitted to OMERO in a single operation. This
causes issues when creating very large tables. In practice you may encounter issues when trying to
export a table with more than ~600 columns, depending on the column name lengths.

|

============ ============ ===============
Supports 2D? Supports 3D? Respects masks?
============ ============ ===============
YES          YES          YES
============ ============ ===============


"""

import functools
import logging
import math
import os
import re
from collections.abc import Iterable

import cellprofiler_core.pipeline
import cellprofiler_core.utilities.legacy
from cellprofiler_core.constants.measurement import AGG_MEAN
from cellprofiler_core.constants.measurement import AGG_MEDIAN
from cellprofiler_core.constants.measurement import AGG_STD_DEV
from cellprofiler_core.constants.measurement import EXPERIMENT
from cellprofiler_core.constants.measurement import M_NUMBER_OBJECT_NUMBER
from cellprofiler_core.constants.measurement import NEIGHBORS
from cellprofiler_core.constants.measurement import OBJECT
from cellprofiler_core.module import Module
from cellprofiler_core.preferences import get_headless
from cellprofiler_core.setting import Binary
from cellprofiler_core.setting import ValidationError
from cellprofiler_core.setting.choice import Choice
from cellprofiler_core.setting.do_something import DoSomething
from cellprofiler_core.setting.subscriber import LabelListSubscriber
from cellprofiler_core.setting.text import Integer, Text
from cellprofiler_core.utilities.measurement import agg_ignore_feature
from cellprofiler_core.constants.measurement import COLTYPE_INTEGER
from cellprofiler_core.constants.measurement import COLTYPE_FLOAT
from cellprofiler_core.constants.measurement import COLTYPE_VARCHAR
from cellprofiler_core.constants.measurement import COLTYPE_BLOB
from cellprofiler_core.constants.measurement import COLTYPE_MEDIUMBLOB
from cellprofiler_core.constants.measurement import COLTYPE_LONGBLOB

import omero
import omero.grid

from omero_helper.connect import CREDENTIALS, login

LOGGER = logging.getLogger(__name__)

##############################################
#
# Keyword for the cached data
#
##############################################
# Measurement column info
D_MEASUREMENT_COLUMNS = "MeasurementColumns"
# OMERO table locations/metadata.
OMERO_TABLE_KEY = "OMERO_tables"

"""The column name for the image number column"""
C_IMAGE_NUMBER = "ImageNumber"

"""The column name for the object number column"""
C_OBJECT_NUMBER = "ObjectNumber"


##############################################
#
# Choices for which objects to include
#
##############################################

"""Put all objects in the database"""
O_ALL = "All"
"""Don't put any objects in the database"""
O_NONE = "None"
"""Select the objects you want from a list"""
O_SELECT = "Select..."


##############################################
#
# Constants for interacting with the OMERO tables API
#
##############################################
# Map from CellProfiler - OMERO column type
COLUMN_TYPES = {
    COLTYPE_INTEGER: omero.grid.LongColumn,
    COLTYPE_FLOAT: omero.grid.DoubleColumn,
    COLTYPE_VARCHAR: omero.grid.StringColumn,
    COLTYPE_BLOB: omero.grid.StringColumn,
    COLTYPE_MEDIUMBLOB: omero.grid.StringColumn,
    COLTYPE_LONGBLOB: omero.grid.StringColumn,
}

# OMERO columns with special meaning
SPECIAL_NAMES = {
    'roi': omero.grid.RoiColumn,
    'image': omero.grid.ImageColumn,
    'dataset': omero.grid.DatasetColumn,
    'well': omero.grid.WellColumn,
    'field': omero.grid.ImageColumn,
    'wellsample': omero.grid.ImageColumn,
    'plate': omero.grid.PlateColumn,
}

# Link annotations needed for each parent type
LINK_TYPES = {
    "Image": omero.model.ImageAnnotationLinkI,
    "Dataset": omero.model.DatasetAnnotationLinkI,
    "Screen": omero.model.ScreenAnnotationLinkI,
    "Plate": omero.model.PlateAnnotationLinkI,
    "Well": omero.model.WellAnnotationLinkI,
}

# OMERO types for each parent type
OBJECT_TYPES = {
    "Image": omero.model.ImageI,
    "Dataset": omero.model.DatasetI,
    "Screen": omero.model.ScreenI,
    "Plate": omero.model.PlateI,
    "Well": omero.model.WellI,
}


class ExportToOMEROTable(Module):
    module_name = "ExportToOMEROTable"
    variable_revision_number = 1
    category = ["File Processing", "Data Tools"]

    def create_settings(self):
        self.target_object_type = Choice(
            "OMERO parent object type",
            ["Image", "Dataset", "Project", "Screen", "Plate"],
            doc="""\
        The created OMERO.table must be associated with an existing object 
        in OMERO. Select the type of object you'd like to attach the table 
        to."""
        )

        self.target_object_id = Integer(
            text="OMERO ID of the parent object",
            minval=1,
            doc="""\
        The created OMERO.table must be associated with an existing object 
        in OMERO. Enter the OMERO ID of the object you'd like to associate 
        the table(s) with. This ID can be found by locating the target object
        in OMERO.web (ID and type is displayed in the right panel).""",
        )


        self.test_connection_button = DoSomething(
            "Test the OMERO connection",
            "Test connection",
            self.test_connection,
            doc="""\
This button test the connection to the OMERO server specified using
the settings entered by the user.""",
        )

        self.want_table_prefix = Binary(
            "Add a prefix to table names?",
            True,
            doc="""\
Select whether you want to add a prefix to your table names. The default
table names are *Per\_Image* for the per-image table and *Per\_Object*
for the per-object table. Adding a prefix can be useful for bookkeeping
purposes.

-  Select "*{YES}*" to add a user-specified prefix to the default table
   names. If you want to distinguish multiple sets of data written to
   the same database, you probably want to use a prefix.
-  Select "*{NO}*" to use the default table names. For a one-time export
   of data, this option is fine.

Whether you chose to use a prefix or not, CellProfiler will warn you if
your choice entails overwriting an existing table.
""".format(
                **{"YES": "Yes", "NO": "No"}
            ),
        )

        self.table_prefix = Text(
            "Table prefix",
            "MyExpt_",
            doc="""\
*(Used if "Add a prefix to table names?" is selected)*

Enter the table prefix you want to use.
""",
        )


        self.wants_agg_mean = Binary(
            "Calculate the per-image mean values of object measurements?",
            True,
            doc="""\
Select "*Yes*" for **ExportToOMEROTable** to calculate population
statistics over all the objects in each image and store the results in
the database. For instance, if you are measuring the area of the Nuclei
objects and you check the box for this option, **ExportToOMEROTable** will
create a column in the Per\_Image table called
“Mean\_Nuclei\_AreaShape\_Area”.

You may not want to use **ExportToOMEROTable** to calculate these
population statistics if your pipeline generates a large number of
per-object measurements; doing so might exceed table column limits.
""",
        )

        self.wants_agg_median = Binary(
            "Calculate the per-image median values of object measurements?",
            False,
            doc="""\
Select "*Yes*" for **ExportToOMEROTable** to calculate population
statistics over all the objects in each image and store the results in
the database. For instance, if you are measuring the area of the Nuclei
objects and you check the box for this option, **ExportToOMEROTable** will
create a column in the Per\_Image table called
“Median\_Nuclei\_AreaShape\_Area”.

You may not want to use **ExportToOMEROTable** to calculate these
population statistics if your pipeline generates a large number of
per-object measurements; doing so might exceed table column limits.
""",
        )

        self.wants_agg_std_dev = Binary(
            "Calculate the per-image standard deviation values of object measurements?",
            False,
            doc="""\
Select "*Yes*" for **ExportToOMEROTable** to calculate population
statistics over all the objects in each image and store the results in
the database. For instance, if you are measuring the area of the Nuclei
objects and you check the box for this option, **ExportToOMEROTable** will
create a column in the Per\_Image table called
“StDev\_Nuclei\_AreaShape\_Area”.

You may not want to use **ExportToOMEROTable** to calculate these
population statistics if your pipeline generates a large number of
per-object measurements; doing so might exceed database column limits. 
""",
        )

        self.objects_choice = Choice(
            "Export measurements for all objects to OMERO?",
            [O_ALL, O_NONE, O_SELECT],
            doc="""\
This option lets you choose the objects whose measurements will be saved
in the Per\_Object and Per\_Well(s) OMERO tables.

-  *{O_ALL}:* Export measurements from all objects.
-  *{O_NONE}:* Do not export data to a Per\_Object table. Save only
   Per\_Image measurements (which nonetheless include
   population statistics from objects).
-  *{O_SELECT}:* Select the objects you want to export from a list.
""".format(
                **{"O_ALL": O_ALL, "O_NONE": O_NONE, "O_SELECT": O_SELECT}
            ),
        )

        self.objects_list = LabelListSubscriber(
            "Select object tables to export",
            [],
            doc="""\
        *(Used only when "Within objects" or "Both" are selected)*

        Select the objects to be measured.""",
        )

    def visible_settings(self):
        result = [self.target_object_type, self.target_object_id,
                  self.test_connection_button, self.want_table_prefix]
        if self.want_table_prefix.value:
            result += [self.table_prefix]
        # Aggregations
        result += [self.wants_agg_mean, self.wants_agg_median, self.wants_agg_std_dev]
        # Table choices (1 / separate object tables, etc)
        result += [self.objects_choice]
        if self.objects_choice == O_SELECT:
            result += [self.objects_list]
        return result

    def settings(self):
        result = [
            self.target_object_type,
            self.target_object_id,
            self.want_table_prefix,
            self.table_prefix,
            self.wants_agg_mean,
            self.wants_agg_median,
            self.wants_agg_std_dev,
            self.objects_choice,
            self.objects_list,
        ]
        return result

    def help_settings(self):
        return [
            self.target_object_type,
            self.target_object_id,
            self.want_table_prefix,
            self.table_prefix,
            self.wants_agg_mean,
            self.wants_agg_median,
            self.wants_agg_std_dev,
            self.objects_choice,
            self.objects_list,
        ]

    def validate_module(self, pipeline):
        if self.want_table_prefix.value:
            if not re.match("^[A-Za-z][A-Za-z0-9_]+$", self.table_prefix.value):
                raise ValidationError("Invalid table prefix", self.table_prefix)

        if self.objects_choice == O_SELECT:
            if len(self.objects_list.value) == 0:
                raise ValidationError(
                    "Please choose at least one object", self.objects_choice
                )

    def validate_module_warnings(self, pipeline):
        """Warn user re: Test mode """
        if pipeline.test_mode:
            raise ValidationError(
                "ExportToOMEROTable does not produce output in Test Mode", self.target_object_id
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
        Establish a connection to OMERO and create the necessary tables."""
        # Reset shared state
        self.get_dictionary().clear()

        pipeline = workspace.pipeline
        if pipeline.test_mode:
            # Don't generate in test mode
            return

        if pipeline.in_batch_mode():
            return True

        # Verify that we're able to connect to a server
        self.connect_to_omero()

        shared_state = self.get_dictionary()

        # Add a list of measurement columns into the module state, and fix their order.
        if D_MEASUREMENT_COLUMNS not in shared_state:
            shared_state[D_MEASUREMENT_COLUMNS] = pipeline.get_measurement_columns()
            shared_state[D_MEASUREMENT_COLUMNS] = self.filter_measurement_columns(
                shared_state[D_MEASUREMENT_COLUMNS]
            )

        # Build a list of tables to create
        column_defs = shared_state[D_MEASUREMENT_COLUMNS]
        desired_tables = ["Image"]
        if self.objects_choice == O_SELECT:
            desired_tables += self.objects_list.value
        elif self.objects_choice == O_ALL:
            desired_tables += self.get_object_names(pipeline)

        # Construct a list of tables in the format (CP name, OMERO name, OMERO ID, CP columns)
        omero_table_list = []
        parent = self.get_omero_parent()

        workspace.display_data.header = ["Output", "Table Name", "OMERO ID", "Server Location"]
        workspace.display_data.columns = []

        for table_name in desired_tables:
            true_name = self.get_table_name(table_name)
            table_cols = [("", "ImageNumber", COLTYPE_INTEGER)]
            if table_name != "Image":
                table_cols.append(("", "ObjectNumber", COLTYPE_INTEGER))
            if table_name == OBJECT:
                target_names = set(self.get_object_names(pipeline))
            else:
                target_names = {table_name}
            table_cols.extend([col for col in column_defs if col[0] in target_names])
            if table_name == "Image":
                # Add any aggregate measurements
                table_cols.extend(self.get_aggregate_columns(workspace.pipeline))
            omero_id = self.create_omero_table(parent, true_name, table_cols)
            omero_table_list.append((table_name, true_name, omero_id, table_cols))
            table_path = f"https://{CREDENTIALS.server}/webclient/omero_table/{omero_id}"
            LOGGER.info(f"Created table at {table_path}")
            workspace.display_data.columns.append((table_name, true_name, omero_id, table_path))

        shared_state[OMERO_TABLE_KEY] = omero_table_list
        LOGGER.debug("Stored OMERO table info into shared state")
        return True

    def get_omero_conn(self):
        self.connect_to_omero()
        return CREDENTIALS.get_gateway()

    def get_omero_parent(self):
        conn = self.get_omero_conn()
        parent_id = self.target_object_id.value
        parent_type = self.target_object_type.value
        old_group = conn.SERVICE_OPTS.getOmeroGroup()
        # Search across groups
        conn.SERVICE_OPTS.setOmeroGroup(-1)
        parent_ob = conn.getObject(parent_type, parent_id)
        if parent_ob is None:
            raise ValueError(f"{parent_type} ID {parent_id} not found on server")
        conn.SERVICE_OPTS.setOmeroGroup(old_group)
        return parent_ob

    def create_omero_table(self, parent, table_name, column_defs):
        """Creates a new OMERO table"""
        conn = self.get_omero_conn()
        parent_type = self.target_object_type.value
        parent_id = self.target_object_id.value
        parent_group = parent.details.group.id.val

        columns = self.generate_omero_columns(column_defs)
        if len(columns) > 500:
            LOGGER.warning(f"Large number of columns in table ({len(columns)})."
                           f"Plugin may encounter issues sending data to OMERO.")
        resources = conn.c.sf.sharedResources(_ctx={
            "omero.group": str(parent_group)})
        repository_id = resources.repositories().descriptions[0].getId().getValue()

        table = None
        try:
            table = resources.newTable(repository_id, table_name, _ctx={
                "omero.group": str(parent_group)})
            table.initialize(columns)
            LOGGER.info("Table creation complete, linking to image")
            orig_file = table.getOriginalFile()

            # create file link
            link_obj = LINK_TYPES[parent_type]()
            target_obj = OBJECT_TYPES[parent_type](parent_id, False)
            # create annotation
            annotation = omero.model.FileAnnotationI()
            # link table to annotation object
            annotation.file = orig_file

            link_obj.link(target_obj, annotation)
            conn.getUpdateService().saveObject(link_obj, _ctx={
                "omero.group": str(parent_group)})
            LOGGER.debug("Saved annotation link")

            LOGGER.info(f"Created table {table_name} under "
                        f"{parent_type} {parent_id}")
            return orig_file.id.val
        except Exception:
            raise
        finally:
            if table is not None:
                table.close()

    def get_omero_table(self, table_id):
        conn = self.get_omero_conn()
        old_group = conn.SERVICE_OPTS.getOmeroGroup()
        # Search across groups
        conn.SERVICE_OPTS.setOmeroGroup(-1)
        table_file = conn.getObject("OriginalFile", table_id)
        if table_file is None:
            raise ValueError(f"OriginalFile ID {table_id} not found on server")
        resources = conn.c.sf.sharedResources()
        table = resources.openTable(table_file._obj)
        conn.SERVICE_OPTS.setOmeroGroup(old_group)
        return table

    def generate_omero_columns(self, column_defs):
        omero_columns = []
        for object_name, measurement, column_type in column_defs:
            if object_name:
                column_name = f"{object_name}_{measurement}"
            else:
                column_name = measurement
            cleaned_name = column_name.replace('/', '\\')
            split_type = column_type.split('(', 1)
            cleaned_type = split_type[0]
            if column_name in SPECIAL_NAMES and column_type.kind == 'i':
                col_class = SPECIAL_NAMES[column_name]
            elif cleaned_type in COLUMN_TYPES:
                col_class = COLUMN_TYPES[cleaned_type]
            else:
                raise NotImplementedError(f"Column type "
                                          f"{cleaned_type} not supported")
            if col_class == omero.grid.StringColumn:
                if len(split_type) == 1:
                    max_len = 128
                else:
                    max_len = int(split_type[1][:-1])
                col = col_class(cleaned_name, "", max_len, [])
            else:
                col = col_class(cleaned_name, "", [])
            omero_columns.append(col)
        return omero_columns

    def run(self, workspace):
        if workspace.pipeline.test_mode:
            return
        shared_state = self.get_dictionary()
        omero_map = shared_state[OMERO_TABLE_KEY]
        # Re-establish server connection
        self.connect_to_omero()

        for table_type, table_name, table_file_id, table_columns in omero_map:
            table = None
            try:
                table = self.get_omero_table(table_file_id)
                self.write_data_to_omero(workspace, table_type, table, table_columns)
            except:
                LOGGER.error(f"Unable to write to table {table_name}", exc_info=True)
                raise
            finally:
                if table is not None:
                    table.close()

    def write_data_to_omero(self, workspace, table_type, omero_table, column_list):
        measurements = workspace.measurements
        table_columns = omero_table.getHeaders()
        # Collect any extra aggregate columns we might need.
        extra_data = {C_IMAGE_NUMBER: measurements.image_set_number}
        if table_type == "Image":
            extra_data.update(measurements.compute_aggregate_measurements(
                measurements.image_set_number, self.agg_names
            ))
        else:
            extra_data[C_OBJECT_NUMBER] = measurements.get_measurement(table_type, M_NUMBER_OBJECT_NUMBER)
            extra_data[C_IMAGE_NUMBER] = [extra_data[C_IMAGE_NUMBER]] * len(extra_data[C_OBJECT_NUMBER])

        for omero_column, (col_type, col_name, _) in zip(table_columns, column_list):
            if col_type:
                true_name = f"{col_type}_{col_name}"
            else:
                true_name = col_name
            if true_name in extra_data:
                value = extra_data[true_name]
            elif not measurements.has_current_measurements(col_type, col_name):
                LOGGER.warning(f"Column not available: {true_name}")
                continue
            else:
                value = measurements.get_measurement(col_type, col_name)
            if isinstance(value, str):
                value = [value]
            elif isinstance(value, Iterable):
                value = list(value)
            elif value is None and isinstance(omero_column, omero.grid.DoubleColumn):
                # Replace None with NaN
                value = [math.nan]
            elif value is None and isinstance(omero_column, omero.grid.LongColumn):
                # Missing values not supported
                value = [-1]
            else:
                value = [value]
            omero_column.values = value
        try:
            omero_table.addData(table_columns)
        except Exception as e:
            LOGGER.error("Data upload was unsuccessful", exc_info=True)
            raise
        LOGGER.info(f"OMERO data uploaded for {table_type}")

    def should_stop_writing_measurements(self):
        """All subsequent modules should not write measurements"""
        return True

    def ignore_object(self, object_name, strict=False):
        """Ignore objects (other than 'Image') if this returns true

        If strict is True, then we ignore objects based on the object selection
        """
        if object_name in (EXPERIMENT, NEIGHBORS,):
            return True
        if strict and self.objects_choice == O_NONE:
            return True
        if strict and self.objects_choice == O_SELECT and object_name != "Image":
            return object_name not in self.objects_list.value
        return False

    def ignore_feature(
        self,
        object_name,
        feature_name,
        strict=False,
    ):
        """Return true if we should ignore a feature"""
        if (
            self.ignore_object(object_name, strict)
            or feature_name.startswith("Number_")
            or feature_name.startswith("Description_")
            or feature_name.startswith("ModuleError_")
            or feature_name.startswith("TimeElapsed_")
            or (feature_name.startswith("ExecutionTime_"))
        ):
            return True
        return False

    def get_aggregate_columns(self, pipeline):
        """Get object aggregate columns for the PerImage table

        pipeline - the pipeline being run
        image_set_list - for cacheing column data
        post_group - true if only getting aggregates available post-group,
                     false for getting aggregates available after run,
                     None to get all

        returns a tuple:
        result[0] - object_name = name of object generating the aggregate
        result[1] - feature name
        result[2] - aggregation operation
        result[3] - column name in Image database
        """
        columns = self.get_pipeline_measurement_columns(pipeline)
        ob_tables = self.get_object_names(pipeline)
        result = []
        for ob_table in ob_tables:
            for obname, feature, ftype in columns:
                if (
                    obname == ob_table
                    and (not self.ignore_feature(obname, feature))
                    and (not agg_ignore_feature(feature))
                ):
                    feature_name = f"{obname}_{feature}"
                    # create per_image aggregate column defs
                    result += [
                        (aggname, feature_name, ftype)
                        for aggname in self.agg_names
                    ]
        return result

    def get_object_names(self, pipeline):
        """Get the names of the objects whose measurements are being taken"""
        column_defs = self.get_pipeline_measurement_columns(pipeline)
        obnames = set([c[0] for c in column_defs])
        #
        # In alphabetical order
        #
        obnames = sorted(obnames)
        return [obname for obname in obnames if not self.ignore_object(obname, True)
                and obname not in ("Image", EXPERIMENT, NEIGHBORS,)]

    @property
    def agg_names(self):
        """The list of selected aggregate names"""
        return [
            name
            for name, setting in (
                (AGG_MEAN, self.wants_agg_mean),
                (AGG_MEDIAN, self.wants_agg_median),
                (AGG_STD_DEV, self.wants_agg_std_dev),
            )
            if setting.value
        ]

    def display(self, workspace, figure):
        figure.set_subplots((1, 1))
        if workspace.pipeline.test_mode:
            figure.subplot_table(0, 0, [["Data not written to database in test mode"]])
        else:
            figure.subplot_table(
                0,
                0,
                workspace.display_data.columns,
                col_labels=workspace.display_data.header,
            )

    def display_post_run(self, workspace, figure):
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

    def get_table_prefix(self):
        if self.want_table_prefix.value:
            return self.table_prefix.value
        return ""

    def get_table_name(self, object_name):
        """Return the table name associated with a given object

        object_name - name of object or "Image", "Object" or "Well"
        """
        return self.get_table_prefix() + "Per_" + object_name

    def get_pipeline_measurement_columns(
        self, pipeline
    ):
        """Get the measurement columns for this pipeline, possibly cached"""
        d = self.get_dictionary()
        if D_MEASUREMENT_COLUMNS not in d:
            d[D_MEASUREMENT_COLUMNS] = pipeline.get_measurement_columns()
            d[D_MEASUREMENT_COLUMNS] = self.filter_measurement_columns(
                d[D_MEASUREMENT_COLUMNS]
            )
        return d[D_MEASUREMENT_COLUMNS]

    def filter_measurement_columns(self, columns):
        """Filter out and properly sort measurement columns"""
        # Unlike ExportToDb we also filter out complex columns here,
        # since post-group measurements can't easily be added to an OMERO.table
        columns = [
            x for x in columns
            if not self.ignore_feature(x[0], x[1], strict=True) and len(x) == 3
        ]

        #
        # put Image ahead of any other object
        # put Number_ObjectNumber ahead of any other column
        #
        def cmpfn(x, y):
            if x[0] != y[0]:
                if x[0] == "Image":
                    return -1
                elif y[0] == "Image":
                    return 1
                else:
                    return cellprofiler_core.utilities.legacy.cmp(x[0], y[0])
            if x[1] == M_NUMBER_OBJECT_NUMBER:
                return -1
            if y[1] == M_NUMBER_OBJECT_NUMBER:
                return 1
            return cellprofiler_core.utilities.legacy.cmp(x[1], y[1])

        columns = sorted(columns, key=functools.cmp_to_key(cmpfn))
        #
        # Remove all but the last duplicate
        #
        duplicate = [
            c0[0] == c1[0] and c0[1] == c1[1]
            for c0, c1 in zip(columns[:-1], columns[1:])
        ] + [False]
        columns = [x for x, y in zip(columns, duplicate) if not y]
        return columns

    def volumetric(self):
        return True
