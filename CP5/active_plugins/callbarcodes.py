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
**CallBarcodes** is used for assigning a barcode to an object based on the channel with the strongest intensity for a given number of cycles.
It is used for optical sequencing by synthesis (SBS).

What do I need as input?
^^^^^^^^^^^^^^^^^^^^^^^^
You need to input a .csv file that contains at least two columns.
One column contains the known barcodes that you will be matching against.
One column contains the corresponding gene/transcript names.
All other columns in the .csv will be ignored.

Before running this module in your pipeline, you need to identify the objects in which you will be calling your barcodes and you will need to have measured the intensities of each object in four channels corresponding to nucleotides A,C,T, and G.
If the background intensities of your four channels are not very well matched, you might want to run the **CompensateColors** module before measuring the object intensities.

What do I get as output?
^^^^^^^^^^^^^^^^^^^^^^^^
To be added

Measurements made by this module
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Within the InputObject.csv, this module outputs the following measurements:
- BarcodeCalled is the n-cycle string of the barcode sequence that was read by the module
- MatchedTo_Barcode is the known barcode that the module best matched to the called barcode
- MatchedTo_ID is an ID number assigned to each known barcode
- MatchedTo_GeneCode is the known gene/transcript name that corresponds to the known barcode
- MatchedTo_Score is the quality of the called barcode to known barcode match, reported as (matching nucleotides)/(total nucleotides) where 1 is a perfect match

Note that CellProfiler cannot create a per-parent mean measurement of a string.

References
^^^^^^^^^^
Optical Pooled Screens in Human Cells.
Feldman D, Singh A, Schmid-Burgk JL, Carlson RJ, Mezger A, Garrity AJ, Zhang F, Blainey PC.
Cell. 2019 Oct 17;179(3):787-799.e17. doi: 10.1016/j.cell.2019.09.016.

|

============ ============ ===============
Supports 2D? Supports 3D? Respects masks?
============ ============ ===============
YES          YES           YES
============ ============ ===============

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
            doc="""\Select the column of barcodes to match against.
""",
        )

        self.metadata_field_tag = cellprofiler_core.setting.choice.Choice(
            "Select the column with gene/transcript barcode names",
            ["No CSV file"],
            choices_fn=self.get_choices,
            doc="""\Select the column with gene/transcript barcode names.
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

        self.has_empty_vector_barcode = cellprofiler_core.setting.Binary(
            "Do you have an empty vector barcode you would like to add to the barcode list?",
            False,
            doc="""\
Select "*{YES}*" to manually enter a sequence that should be added to the uploaded barcode
list with the gene name of "EmptyVector". This can be helpful when there is a consistent
backbone sequence to look out for in every barcoding set).""".format(
                **{"YES": "Yes"}
            ),
        )

        self.empty_vector_barcode_sequence = cellprofiler_core.setting.text.Text(
            "What is the empty vector sequence?",
            "AAAAAAAAAAAAAAA",
            doc="""\
Enter the sequence that represents barcoding reads of an empty vector""",
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
            self.has_empty_vector_barcode,
            self.empty_vector_barcode_sequence,
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

        if self.has_empty_vector_barcode:
            result += [self.empty_vector_barcode_sequence]

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

        objectcount = len(
            measurements.get_current_measurement(
                self.input_object_name.value, listofmeasurements[0]
            )
        )

        calledbarcodes, quality_scores = self.callonebarcode(
            measurements_for_calls,
            measurements,
            self.input_object_name.value,
            self.ncycles.value,
            objectcount,
        )

        workspace.measurements.add_measurement(
            self.input_object_name.value,
            "_".join([C_CALL_BARCODES, "BarcodeCalled"]),
            calledbarcodes,
        )

        workspace.measurements.add_measurement(
            self.input_object_name.value,
            "_".join([C_CALL_BARCODES, "MeanQualityScore"]),
            quality_scores,
        )

        barcodes = self.barcodeset(
            self.metadata_field_barcode.value, self.metadata_field_tag.value
        )

        cropped_barcode_dict = {
            y[: self.ncycles.value]: y for y in list(barcodes.keys())
        }

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
            eachscore, eachmatch = self.queryall(cropped_barcode_dict, eachbarcode)
            scorelist.append(eachscore)
            matchedbarcode.append(eachmatch)
            m_id, m_code = barcodes[eachmatch]
            matchedbarcodeid.append(m_id)
            matchedbarcodecode.append(m_code)
            if self.wants_call_image:
                pixel_data_call = numpy.where(
                    labels == count, barcodes[eachmatch][0], pixel_data_call
                )
            if self.wants_score_image:
                pixel_data_score = numpy.where(
                    labels == count, 65535 * eachscore, pixel_data_score
                )
            count += 1

        imagemeanscore = numpy.mean(scorelist)

        workspace.measurements.add_measurement(
            "Image", "_".join([C_CALL_BARCODES, "MeanBarcodeScore"]), imagemeanscore
        )

        imagemeanquality = numpy.mean(quality_scores)

        workspace.measurements.add_measurement(
            "Image", "_".join([C_CALL_BARCODES, "MeanQualityScore"]), imagemeanquality
        )

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

        if self.show_window:
            workspace.display_data.col_labels = (
                "Image Mean Score",
                "Image Mean Quality Score",
            )
            workspace.display_data.statistics = [imagemeanscore, imagemeanquality]

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

    def callonebarcode(
        self, measurementdict, measurements, object_name, ncycles, objectcount
    ):

        master_cycles = []
        score_array = numpy.zeros([ncycles, objectcount])

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
            argmax_per_obj = numpy.argmax(cycle_measures_perobj, 1)
            max_per_obj = numpy.max(cycle_measures_perobj, 1)
            sum_per_obj = numpy.sum(cycle_measures_perobj, 1)
            score_per_obj = max_per_obj / sum_per_obj
            argmax_per_obj = list(argmax_per_obj)
            argmax_per_obj = [cyclecode[x] for x in argmax_per_obj]

            master_cycles.append(list(argmax_per_obj))
            score_array[eachcycle - 1] = score_per_obj

        mean_per_object = score_array.mean(axis=0)

        return list(map("".join, zip(*master_cycles))), mean_per_object

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
        if self.has_empty_vector_barcode:
            barcodeset[self.empty_vector_barcode_sequence.value] = (
                count,
                "EmptyVector",
            )
        return barcodeset

    def queryall(self, cropped_barcode_dict, query):

        cropped_barcode_list = list(cropped_barcode_dict.keys())

        if query in cropped_barcode_list:
            # is a perfect match
            return 1, cropped_barcode_dict[query]

        else:
            scoredict = {
                sum([1 for x in range(len(query)) if query[x] == y[x]])
                / float(len(query)): y
                for y in cropped_barcode_list
            }
            scores = list(scoredict.keys())
            scores.sort(reverse=True)
            return scores[0], cropped_barcode_dict[scoredict[scores[0]]]

    def get_measurement_columns(self, pipeline):

        input_object_name = self.input_object_name.value

        result = [
            (
                "Image",
                "_".join([C_CALL_BARCODES, "MeanBarcodeScore"]),
                cellprofiler_core.constants.measurement.COLTYPE_FLOAT,
            ),
            (
                "Image",
                "_".join([C_CALL_BARCODES, "MeanQualityScore"]),
                cellprofiler_core.constants.measurement.COLTYPE_FLOAT,
            ),
        ]

        result += [
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
            (
                input_object_name,
                "_".join([C_CALL_BARCODES, "MeanQualityScore"]),
                cellprofiler_core.constants.measurement.COLTYPE_FLOAT,
            ),
        ]

        return result

    def get_categories(self, pipeline, object_name):
        if object_name == self.input_object_name or object_name == "Image":
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
                "MeanQualityScore",
            ]

        elif object_name == object_name == "Image":
            return [
                "MeanBarcodeScore",
                "MeanQualityScore",
            ]

        return []
