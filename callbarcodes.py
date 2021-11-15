# coding=utf-8

#################################
#
# Imports from useful Python libraries
#
#################################

import csv
import numpy
import os
import re
import urllib.request, urllib.error, urllib.parse

try:
    from io import StringIO
except ImportError:
    from io import StringIO

#################################
#
# Imports from CellProfiler
#
##################################

from cellprofiler.modules import _help
import cellprofiler_core.image
import cellprofiler_core.module
import cellprofiler_core.measurement
import cellprofiler_core.object
import cellprofiler_core.setting
import cellprofiler_core.constants.setting
import cellprofiler_core.setting.text
import cellprofiler_core.setting.choice
import cellprofiler_core.setting.subscriber
import cellprofiler_core.utilities.image
import cellprofiler_core.preferences
import cellprofiler_core.constants.measurement

__doc__ = """\
CallBarcodes
============

**CallBarcodes** - This module calls barcodes.

|

============ ============ ===============
Supports 2D? Supports 3D? Respects masks?
============ ============ ===============
YES          Yes           YES
============ ============ ===============


What do I need as input?
^^^^^^^^^^^^^^^^^^^^^^^^
To be added 

What do I get as output?
^^^^^^^^^^^^^^^^^^^^^^^^
To be added

Measurements made by this module
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
To be added

References
^^^^^^^^^^
Optical Pooled Screens in Human Cells.
Feldman D, Singh A, Schmid-Burgk JL, Carlson RJ, Mezger A, Garrity AJ, Zhang F, Blainey PC.
Cell. 2019 Oct 17;179(3):787-799.e17. doi: 10.1016/j.cell.2019.09.016.
"""

C_CALL_BARCODES = "Barcode"


class CallBarcodes(cellprofiler_core.module.Module):

    module_name = "CallBarcodes"
    category = "Data Tools"
    variable_revision_number = 1

    def create_settings(self):
        self.csv_directory = cellprofiler_core.setting.text.Directory(
            "Input data file location",
            allow_metadata=False,
            doc="""\
Select the folder containing the CSV file to be loaded. {IO_FOLDER_CHOICE_HELP_TEXT}
""".format(
                **{"IO_FOLDER_CHOICE_HELP_TEXT": _help.IO_FOLDER_CHOICE_HELP_TEXT}
            ),
        )

        def get_directory_fn():
            """Get the directory for the CSV file name"""
            return self.csv_directory.get_absolute_path()

        def set_directory_fn(path):
            dir_choice, custom_path = self.csv_directory.get_parts_from_path(path)
            self.csv_directory.join_parts(dir_choice, custom_path)

        self.csv_file_name = cellprofiler_core.setting.text.Filename(
            "Name of the file",
            "None",
            doc="""Provide the file name of the CSV file containing the data you want to load.""",
            get_directory_fn=get_directory_fn,
            set_directory_fn=set_directory_fn,
            browse_msg="Choose CSV file",
            exts=[("Data file (*.csv)", "*.csv"), ("All files (*.*)", "*.*")],
        )

        self.input_object_name = cellprofiler_core.setting.subscriber.LabelSubscriber(
            text="Input object name",
            doc="These are the objects that the module operates on.",
        )

        self.ncycles = cellprofiler_core.setting.text.Integer(
            doc="""\
Enter the number of cycles present in the data.
""",
            text="Number of cycles",
            value=8,
        )
        self.cycle1measure = cellprofiler_core.setting.Measurement(
            "Select one of the measures from Cycle 1 to use for calling",
            self.input_object_name.get_value,
            "AreaShape_Area",
            doc="""\
This measurement should be """,
        )

        self.metadata_field_barcode = cellprofiler_core.setting.choice.Choice(
            "Select the column of barcodes to match against",
            ["No CSV file"],
            choices_fn=self.get_choices,
            doc="""\
""",
        )

        self.metadata_field_tag = cellprofiler_core.setting.choice.Choice(
            "Select the column with gene/transcript barcode names",
            ["No CSV file"],
            choices_fn=self.get_choices,
            doc="""\
""",
        )

        self.wants_call_image = cellprofiler_core.setting.Binary(
            "Retain an image of the barcodes color coded by call?",
            False,
            doc="""\
Select "*{YES}*" to retain the image of the objects color-coded
according to which line of the CSV their barcode call matches to,
for use later in the pipeline (for example, to be saved by a **SaveImages**
module).""".format(
                **{"YES": "Yes"}
            ),
        )

        self.outimage_calls_name = cellprofiler_core.setting.text.ImageName(
            "Enter the called barcode image name",
            "None",
            doc="""\
*(Used only if the called barcode image is to be retained for later use in the pipeline)*

Enter the name to be given to the called barcode image.""",
        )

        self.wants_score_image = cellprofiler_core.setting.Binary(
            "Retain an image of the barcodes color coded by score match?",
            False,
            doc="""\
Select "*{YES}*" to retain the image of the objects where the intensity of the spot matches
indicates the match score between the called barcode and its closest match,
for use later in the pipeline (for example, to be saved by a **SaveImages**
module).""".format(
                **{"YES": "Yes"}
            ),
        )

        self.outimage_score_name = cellprofiler_core.setting.text.ImageName(
            "Enter the barcode score image name",
            "None",
            doc="""\
*(Used only if the barcode score image is to be retained for later use in the pipeline)*

Enter the name to be given to the barcode score image.""",
        )


    def settings(self):
        return [
            self.ncycles,
            self.input_object_name,
            self.cycle1measure,
            self.csv_directory,
            self.csv_file_name,
            self.metadata_field_barcode,
            self.metadata_field_tag,
            self.wants_call_image,
            self.outimage_calls_name,
            self.wants_score_image,
            self.outimage_score_name,
        ]

    def visible_settings(self):
        result = [
            self.ncycles,
            self.input_object_name,
            self.cycle1measure,
            self.csv_directory,
            self.csv_file_name,
            self.metadata_field_barcode,
            self.metadata_field_tag,
            self.wants_call_image,
            self.wants_score_image,
        ]

        if self.wants_call_image:
            result += [self.outimage_calls_name]

        if self.wants_score_image:
            result += [self.outimage_score_name]

        return result

    def validate_module(self, pipeline):
        csv_path = self.csv_path

        if not os.path.isfile(csv_path):
            raise cellprofiler_core.setting.ValidationError(
                "No such CSV file: %s" % csv_path, self.csv_file_name
            )

        try:
            self.open_csv()
        except IOError as e:
            import errno

            if e.errno == errno.EWOULDBLOCK:
                raise cellprofiler_core.setting.ValidationError(
                    "Another program (Excel?) is locking the CSV file %s."
                    % self.csv_path,
                    self.csv_file_name,
                )
            else:
                raise cellprofiler_core.setting.ValidationError(
                    "Could not open CSV file %s (error: %s)" % (self.csv_path, e),
                    self.csv_file_name,
                )

        try:
            self.get_header()
        except Exception as e:
            raise cellprofiler_core.setting.ValidationError(
                "The CSV file, %s, is not in the proper format."
                " See this module's help for details on CSV format. (error: %s)"
                % (self.csv_path, e),
                self.csv_file_name,
            )

    @property
    def csv_path(self):
        """The path and file name of the CSV file to be loaded"""
        path = self.csv_directory.get_absolute_path()
        return os.path.join(path, self.csv_file_name.value)

    def open_csv(self, do_not_cache=False):
        """Open the csv file or URL, returning a file descriptor"""

        print(f"self.csv_path: {self.csv_path}")

        if cellprofiler_core.preferences.is_url_path(self.csv_path):
            if self.csv_path not in self.header_cache:
                self.header_cache[self.csv_path] = {}

            entry = self.header_cache[self.csv_path]

            if "URLEXCEPTION" in entry:
                raise entry["URLEXCEPTION"]

            if "URLDATA" in entry:
                fd = StringIO(entry["URLDATA"])
            else:
                if do_not_cache:
                    raise RuntimeError("Need to fetch URL manually.")

                try:
                    url = cellprofiler_core.utilities.image.generate_presigned_url(
                        self.csv_path
                    )
                    url_fd = urllib.request.urlopen(url)
                except Exception as e:
                    entry["URLEXCEPTION"] = e

                    raise e

                fd = StringIO()

                while True:
                    text = url_fd.read()

                    if len(text) == 0:
                        break

                    fd.write(text)

                fd.seek(0)

                entry["URLDATA"] = fd.getvalue()

            return fd
        else:
            return open(self.csv_path, "r")

    def get_header(self, do_not_cache=False):
        """Read the header fields from the csv file

        Open the csv file indicated by the settings and read the fields
        of its first line. These should be the measurement columns.
        """
        with open(self.csv_path, "r") as fp:
            reader = csv.DictReader(fp)

            return reader.fieldnames

    def get_choices(self, pipeline):
        choices = self.get_header()

        if not choices:
            choices = ["No CSV file"]

        return choices

    def run(self, workspace):

        measurements = workspace.measurements
        listofmeasurements = measurements.get_feature_names(
            self.input_object_name.value
        )

        measurements_for_calls = self.getallbarcodemeasurements(
            listofmeasurements, self.ncycles.value, self.cycle1measure.value
        )

        calledbarcodes = self.callonebarcode(
            measurements_for_calls,
            measurements,
            self.input_object_name.value,
            self.ncycles.value,
        )

        workspace.measurements.add_measurement(
            self.input_object_name.value,
            "_".join([C_CALL_BARCODES, "BarcodeCalled"]),
            calledbarcodes,
        )

        barcodes = self.barcodeset(
            self.metadata_field_barcode.value, self.metadata_field_tag.value
        )

        scorelist = []
        matchedbarcode = []
        matchedbarcodecode = []
        matchedbarcodeid = []
        if self.wants_call_image or self.wants_score_image:
            objects = workspace.object_set.get_objects(self.input_object_name.value)
            labels = objects.segmented
            pixel_data_call = objects.segmented
            pixel_data_score = objects.segmented
        count = 1
        for eachbarcode in calledbarcodes:
            eachscore, eachmatch = self.queryall(barcodes, eachbarcode)
            scorelist.append(eachscore)
            matchedbarcode.append(eachmatch)
            matchedbarcodeid.append(barcodes[eachmatch][0])
            matchedbarcodecode.append(barcodes[eachmatch][1])
            if self.wants_call_image:
                pixel_data_call = numpy.where(
                    labels == count, barcodes[eachmatch][0], pixel_data_call
                )
            if self.wants_score_image:
                pixel_data_score = numpy.where(
                    labels == count, 65535 * eachscore, pixel_data_score
                )
            count += 1
        workspace.measurements.add_measurement(
            self.input_object_name.value,
            "_".join([C_CALL_BARCODES, "MatchedTo_Barcode"]),
            matchedbarcode,
        )
        workspace.measurements.add_measurement(
            self.input_object_name.value,
            "_".join([C_CALL_BARCODES, "MatchedTo_ID"]),
            matchedbarcodeid,
        )
        workspace.measurements.add_measurement(
            self.input_object_name.value,
            "_".join([C_CALL_BARCODES, "MatchedTo_GeneCode"]),
            matchedbarcodecode,
        )
        workspace.measurements.add_measurement(
            self.input_object_name.value,
            "_".join([C_CALL_BARCODES, "MatchedTo_Score"]),
            scorelist,
        )
        if self.wants_call_image:
            workspace.image_set.add(
                self.outimage_calls_name.value,
                cellprofiler_core.image.Image(
                    pixel_data_call.astype("uint16"), convert=False
                ),
            )
        if self.wants_score_image:
            workspace.image_set.add(
                self.outimage_score_name.value,
                cellprofiler_core.image.Image(
                    pixel_data_score.astype("uint16"), convert=False
                ),
            )

        statistics = [["Feature", "Mean", "Median", "SD"]]

        workspace.display_data.statistics = statistics


    def display(self, workspace, figure):
        statistics = workspace.display_data.statistics

        figure.set_subplots((1, 1))

        figure.subplot_table(0, 0, statistics)

    def getallbarcodemeasurements(self, measurements, ncycles, examplemeas):
        stem = re.split("Cycle", examplemeas)[0]
        measurementdict = {}
        for eachmeas in measurements:
            if stem in eachmeas:
                to_parse = re.split("Cycle", eachmeas)[1]
                find_cycle = re.search("[0-9]{1,2}", to_parse)
                parsed_cycle = int(find_cycle.group(0))
                find_base = re.search("[A-Z]", to_parse)
                parsed_base = find_base.group(0)
                if parsed_cycle <= ncycles:
                    if parsed_cycle not in list(measurementdict.keys()):
                        measurementdict[parsed_cycle] = {eachmeas: parsed_base}
                    else:
                        measurementdict[parsed_cycle].update({eachmeas: parsed_base})
        return measurementdict

    def callonebarcode(self, measurementdict, measurements, object_name, ncycles):

        master_cycles = []

        for eachcycle in range(1, ncycles + 1):
            cycles_measures_perobj = []
            cyclecode = []
            cycledict = measurementdict[eachcycle]
            cyclemeasures = list(cycledict.keys())
            for eachmeasure in cyclemeasures:
                cycles_measures_perobj.append(
                    measurements.get_current_measurement(object_name, eachmeasure)
                )
                cyclecode.append(measurementdict[eachcycle][eachmeasure])
            cycle_measures_perobj = numpy.transpose(numpy.array(cycles_measures_perobj))
            max_per_obj = numpy.argmax(cycle_measures_perobj, 1)
            max_per_obj = list(max_per_obj)
            max_per_obj = [cyclecode[x] for x in max_per_obj]
            master_cycles.append(list(max_per_obj))

        return list(map("".join, list(zip(*master_cycles))))

    def barcodeset(self, barcodecol, genecol):
        fd = self.open_csv()
        reader = csv.DictReader(fd)
        barcodeset = {}
        count = 1
        for row in reader:
            if len(row[barcodecol]) != 0:
                barcodeset[row[barcodecol]] = (count, row[genecol])
                count += 1
        fd.close()
        return barcodeset

    def queryall(self, barcodeset, query):
        barcodelist = list(barcodeset.keys())
        scoredict = {
            sum([1 for x in range(len(query)) if query[x] == y[x]])
            / float(len(query)): y
            for y in barcodelist
        }
        scores = list(scoredict.keys())
        scores.sort(reverse=True)
        return scores[0], scoredict[scores[0]]

    def get_measurement_columns(self, pipeline):

        input_object_name = self.input_object_name.value

        return [
            (
                input_object_name,
                "_".join([C_CALL_BARCODES, "BarcodeCalled"]),
                cellprofiler_core.constants.measurement.COLTYPE_VARCHAR,
            ),
            (
                input_object_name,
                "_".join([C_CALL_BARCODES, "MatchedTo_Barcode"]),
                cellprofiler_core.constants.measurement.COLTYPE_VARCHAR,
            ),
            (
                input_object_name,
                "_".join([C_CALL_BARCODES, "MatchedTo_ID"]),
                cellprofiler_core.constants.measurement.COLTYPE_INTEGER,
            ),
            (
                input_object_name,
                "_".join([C_CALL_BARCODES, "MatchedTo_GeneCode"]),
                cellprofiler_core.constants.measurement.COLTYPE_VARCHAR,
            ),
            (
                input_object_name,
                "_".join([C_CALL_BARCODES, "MatchedTo_Score"]),
                cellprofiler_core.constants.measurement.COLTYPE_FLOAT,
            ),
        ]

    def get_categories(self, pipeline, object_name):
        if object_name == self.input_object_name:
            return [C_CALL_BARCODES]

        return []

    def get_measurements(self, pipeline, object_name, category):
        if object_name == self.input_object_name and category == C_CALL_BARCODES:
            return [
                "BarcodeCalled",
                "MatchedTo_Barcode",
                "MatchedTo_ID",
                "MatchedTo_GeneCode",
                "MatchedTo_Score",
            ]

        return []
