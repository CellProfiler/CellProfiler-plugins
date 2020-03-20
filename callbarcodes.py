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
import urllib2

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

#################################
#
# Imports from CellProfiler
#
##################################

from cellprofiler.modules import _help
import cellprofiler.image
import cellprofiler.module
import cellprofiler.measurement
import cellprofiler.object
import cellprofiler.setting


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


class CallBarcodes(cellprofiler.module.Module):
    module_name = "CallBarcodes"
    category = "Data Tools"
    variable_revision_number = 1

    def create_settings(self):
        self.csv_directory = cellprofiler.setting.DirectoryPath(
            "Input data file location", allow_metadata=False, doc="""\
Select the folder containing the CSV file to be loaded. {IO_FOLDER_CHOICE_HELP_TEXT}
""".format(**{
                "IO_FOLDER_CHOICE_HELP_TEXT": _help.IO_FOLDER_CHOICE_HELP_TEXT
            }))

        def get_directory_fn():
            '''Get the directory for the CSV file name'''
            return self.csv_directory.get_absolute_path()

        def set_directory_fn(path):
            dir_choice, custom_path = self.csv_directory.get_parts_from_path(path)
            self.csv_directory.join_parts(dir_choice, custom_path)

        self.csv_file_name = cellprofiler.setting.FilenameText(
            "Name of the file",
            cellprofiler.setting.NONE,
            doc="""Provide the file name of the CSV file containing the data you want to load.""",
            get_directory_fn=get_directory_fn,
            set_directory_fn=set_directory_fn,
            browse_msg="Choose CSV file",
            exts=[("Data file (*.csv)", "*.csv"), ("All files (*.*)", "*.*")])

        self.input_object_name = cellprofiler.setting.ObjectNameSubscriber(
            text="Input object name",
            doc="These are the objects that the module operates on.")


        self.ncycles = cellprofiler.setting.Integer(
            doc="""\
Enter the number of cycles present in the data.
""",
            text="Number of cycles",
            value=8
        )
        self.cycle1measure=cellprofiler.setting.Measurement(
            "Select one of the measures from Cycle 1 to use for calling",
            self.input_object_name.get_value,'AreaShape_Area',
            doc="""\
This measurement should be """)

        self.metadata_field_barcode = cellprofiler.setting.Choice(
            "Select the column of barcodes to match against", ["No CSV file"], choices_fn=self.get_choices,
            doc="""\
""")

        self.metadata_field_tag = cellprofiler.setting.Choice(
            "Select the column with gene/transcript barcode names", ["No CSV file"], choices_fn=self.get_choices,
            doc="""\
""")

        self.number_matches = cellprofiler.setting.Integer(
            doc="""\
Enter how many matches to return.  The Barcode, ID, GeneCode, and Score will be returned for each of the top N matches.
Use 1 to return only the best match."
""",
            text="Number of top N matches to return",
            value=1
        )

        self.has_empty_vector_barcode = cellprofiler.setting.Binary(
            "Do you have an empty vector barcode you would like to add to the barcode list?", False, doc="""\
Select "*{YES}*" to manually enter a sequence that should be added to the uploaded barcode 
list with the gene name of "EmptyVector". This can be helpful when there is a consistent
backbone sequence to look out for in every barcoding set).""" .format(**{"YES": cellprofiler.setting.YES
                       }))

        self.empty_vector_barcode_sequence = cellprofiler.setting.Text(
            "What is the empty vector sequence?", "AAAAAAAAAAAAAAA", doc="""\
Enter the sequence that represents barcoding reads of an empty vector"""
        )

        self.wants_call_image = cellprofiler.setting.Binary(
            "Retain an image of the barcodes color coded by call?", False, doc="""\
Select "*{YES}*" to retain the image of the objects color-coded
according to which line of the CSV their barcode call best matches to, 
for use later in the pipeline (for example, to be saved by a **SaveImages** 
module).""" .format(**{"YES": cellprofiler.setting.YES
                }))

        self.outimage_calls_name = cellprofiler.setting.ImageNameProvider(
        "Enter the called barcode image name", cellprofiler.setting.NONE, doc="""\
*(Used only if the called barcode image is to be retained for later use in the pipeline)*

Enter the name to be given to the called barcode image.""")

        self.wants_score_image = cellprofiler.setting.Binary(
            "Retain an image of the barcodes color coded by score match?", False, doc="""\
Select "*{YES}*" to retain the image of the objects where the intensity of the spot matches
indicates the match score between the called barcode and its closest match, 
for use later in the pipeline (for example, to be saved by a **SaveImages** 
module).""" .format(**{"YES": cellprofiler.setting.YES
                       }))

        self.outimage_score_name = cellprofiler.setting.ImageNameProvider(
        "Enter the barcode score image name", cellprofiler.setting.NONE, doc="""\
*(Used only if the barcode score image is to be retained for later use in the pipeline)*

Enter the name to be given to the barcode score image.""")

    def settings(self):
        return [
            self.ncycles,
            self.input_object_name,
            self.cycle1measure,
            self.csv_directory,
            self.csv_file_name,
            self.metadata_field_barcode,
            self.metadata_field_tag,
            self.number_matches,
            self.has_empty_vector_barcode,
            self.empty_vector_barcode_sequence,
            self.wants_call_image,
            self.outimage_calls_name,
            self.wants_score_image,
            self.outimage_score_name
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
            self.number_matches,
            self.has_empty_vector_barcode]

        if self.has_empty_vector_barcode:
            result += [self.empty_vector_barcode_sequence]

        result += [self.wants_call_image]

        if self.wants_call_image:
            result += [self.outimage_calls_name]

        result += [self.wants_score_image]

        if self.wants_score_image:
            result += [self.outimage_score_name]

        return result

    def validate_module(self, pipeline):
        csv_path = self.csv_path

        if not os.path.isfile(csv_path):
            raise cellprofiler.setting.ValidationError("No such CSV file: %s" % csv_path,
                                                           self.csv_file_name)

        try:
            self.open_csv()
        except IOError as e:
            import errno
            if e.errno == errno.EWOULDBLOCK:
                raise cellprofiler.setting.ValidationError("Another program (Excel?) is locking the CSV file %s." %
                                                           self.csv_path, self.csv_file_name)
            else:
                raise cellprofiler.setting.ValidationError("Could not open CSV file %s (error: %s)" %
                                                           (self.csv_path, e), self.csv_file_name)

        try:
            self.get_header()
        except Exception as e:
            raise cellprofiler.setting.ValidationError(
                "The CSV file, %s, is not in the proper format."
                " See this module's help for details on CSV format. (error: %s)" % (self.csv_path, e),
                self.csv_file_name)

    @property
    def csv_path(self):
        '''The path and file name of the CSV file to be loaded'''
        path = self.csv_directory.get_absolute_path()
        return os.path.join(path, self.csv_file_name.value)

    def open_csv(self, do_not_cache=False):
        '''Open the csv file or URL, returning a file descriptor'''
        global header_cache

        if cellprofiler.preferences.is_url_path(self.csv_path):
            if self.csv_path not in header_cache:
                header_cache[self.csv_path] = {}
            entry = header_cache[self.csv_path]
            if "URLEXCEPTION" in entry:
                raise entry["URLEXCEPTION"]
            if "URLDATA" in entry:
                fd = StringIO(entry["URLDATA"])
            else:
                if do_not_cache:
                    raise RuntimeError('Need to fetch URL manually.')
                try:
                    url = cellprofiler.misc.generate_presigned_url(self.csv_path)
                    url_fd = urllib2.urlopen(url)
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
            return open(self.csv_path, 'rb')

    def get_header(self, do_not_cache=False):
        '''Read the header fields from the csv file

        Open the csv file indicated by the settings and read the fields
        of its first line. These should be the measurement columns.
        '''
        fd = self.open_csv(do_not_cache=do_not_cache)
        reader = csv.reader(fd)
        header = next(reader)
        fd.close()
        return header

    def get_choices(self,pipeline):
        try:
            choices = self.get_header()
        except:
            choices = ["No CSV file"]
        return choices

    def run(self, workspace):
        measurements = workspace.measurements
        listofmeasurements = measurements.get_feature_names(self.input_object_name.value)

        objectcount = len(measurements.get_current_measurement(self.input_object_name.value,listofmeasurements[0]))

        measurements_for_calls = self.getallbarcodemeasurements(listofmeasurements, self.ncycles.value,
                                                                self.cycle1measure.value)

        calledbarcodes, avgbasescore, basescorelist = self.callonebarcode(measurements_for_calls, measurements, self.input_object_name.value,
                                            self.ncycles.value, objectcount)

        workspace.measurements.add_measurement(self.input_object_name.value, '_'.join([C_CALL_BARCODES,'BarcodeCalled']),
                                     calledbarcodes)

        workspace.measurements.add_measurement(self.input_object_name.value,'_'.join([C_CALL_BARCODES,'MeanQualityScore']),
                                     avgbasescore)

        for eachcycle in range(1,self.ncycles.value+1):
            workspace.measurements.add_measurement(self.input_object_name.value,
                                    '_'.join([C_CALL_BARCODES,'Cycle'+str.zfill(str(eachcycle),2)+'QualityScore']),
                                    basescorelist[eachcycle-1])

        imagemean = numpy.mean(avgbasescore)

        workspace.measurements.add_measurement(cellprofiler.measurement.IMAGE, '_'.join([C_CALL_BARCODES,'ImageMeanQualityScore']), imagemean)

        barcodes = self.barcodeset(self.metadata_field_barcode.value, self.metadata_field_tag.value)

        Nmatchdigits = len(str(self.number_matches.value))

        scoredict = {x:[] for x in range(1,self.number_matches.value + 1)}
        matchedbarcode = {x:[] for x in range(1,self.number_matches.value + 1)}
        matchedbarcodecode = {x:[] for x in range(1,self.number_matches.value + 1)}
        matchedbarcodeid = {x:[] for x in range(1,self.number_matches.value + 1)}
        if self.wants_call_image:
            objects = workspace.object_set.get_objects(self.input_object_name.value)
            labels = objects.segmented
            pixel_data_call = objects.segmented
            pixel_data_score = objects.segmented
        count = 1
        for eachbarcode in calledbarcodes:
            scoreresults = self.queryall(barcodes, eachbarcode)
            for eachmatchN in range(1,self.number_matches.value+1):
                eachscore, eachmatch = scoreresults[eachmatchN]
                scoredict[eachmatchN].append(eachscore)
                matchedbarcode[eachmatchN].append(eachmatch)
                matchedbarcodeid[eachmatchN].append(barcodes[eachmatch][0])
                matchedbarcodecode[eachmatchN].append(barcodes[eachmatch][1])
                if eachmatchN == 1:
                    if self.wants_call_image:
                        pixel_data_call = numpy.where(labels==count,barcodes[eachmatch][0],pixel_data_call)
                    if self.wants_score_image:
                        pixel_data_score = numpy.where(labels==count,65535*eachscore,pixel_data_score)
            count += 1
        for eachmatchN in range(1,self.number_matches.value+1):
            workspace.measurements.add_measurement(self.input_object_name.value, '_'.join([C_CALL_BARCODES,'Match'+str.zfill(str(eachmatchN),Nmatchdigits)+'_Barcode']),
                                         matchedbarcode[eachmatchN])
            workspace.measurements.add_measurement(self.input_object_name.value, '_'.join([C_CALL_BARCODES,'Match'+str.zfill(str(eachmatchN),Nmatchdigits)+'_ID']),
                                         matchedbarcodeid[eachmatchN])
            workspace.measurements.add_measurement(self.input_object_name.value, '_'.join([C_CALL_BARCODES,'Match'+str.zfill(str(eachmatchN),Nmatchdigits)+'_GeneCode']),
                                         matchedbarcodecode[eachmatchN])
            workspace.measurements.add_measurement(self.input_object_name.value, '_'.join([C_CALL_BARCODES,'Match'+str.zfill(str(eachmatchN),Nmatchdigits)+'_Score']),
                                         scoredict[eachmatchN])
        if self.wants_call_image:
            workspace.image_set.add(self.outimage_calls_name.value,cellprofiler.image.Image(pixel_data_call.astype("uint16"),
                                                                                      convert = False ))
        if self.wants_score_image:
            workspace.image_set.add(self.outimage_score_name.value,cellprofiler.image.Image(pixel_data_score.astype("uint16"),
                                                                                        convert = False ))

    def getallbarcodemeasurements(self, measurements, ncycles, examplemeas):
        stem = re.split('Cycle',examplemeas)[0]
        measurementdict = {}
        for eachmeas in measurements:
            if stem in eachmeas:
                to_parse = re.split('Cycle',eachmeas)[1]
                find_cycle = re.search('[0-9]{1,2}',to_parse)
                parsed_cycle = int(find_cycle.group(0))
                find_base = re.search('[A-Z]',to_parse)
                parsed_base = find_base.group(0)
                if parsed_cycle <= ncycles:
                    if parsed_cycle not in measurementdict.keys():
                        measurementdict[parsed_cycle] = {eachmeas:parsed_base}
                    else:
                        measurementdict[parsed_cycle].update({eachmeas:parsed_base})
        return measurementdict

    def callonebarcode(self, measurementdict, measurements, object_name, ncycles, objectcount):

        master_cycles = []
        score_array = numpy.zeros([ncycles,objectcount])

        for eachcycle in range(1,ncycles+1):
            cycles_measures_perobj = []
            cyclecode = []
            cycledict = measurementdict[eachcycle]
            cyclemeasures = cycledict.keys()
            for eachmeasure in cyclemeasures:
                cycles_measures_perobj.append(measurements.get_current_measurement(object_name, eachmeasure))
                cyclecode.append(measurementdict[eachcycle][eachmeasure])
            cycle_measures_perobj = numpy.transpose(numpy.array(cycles_measures_perobj))
            argmax_per_obj = numpy.argmax(cycle_measures_perobj,1)
            max_per_obj = numpy.max(cycle_measures_perobj,1)
            sum_per_obj = numpy.sum(cycle_measures_perobj,1)
            score_per_obj = max_per_obj/sum_per_obj
            argmax_per_obj = list(argmax_per_obj)
            argmax_per_obj = [cyclecode[x] for x in argmax_per_obj]

            master_cycles.append(list(argmax_per_obj))
            score_array[eachcycle-1] = score_per_obj

        mean_per_object = score_array.mean(axis=0)

        return list(map("".join, zip(*master_cycles))), mean_per_object, score_array


    def barcodeset(self, barcodecol, genecol):
        fd = self.open_csv()
        reader = csv.DictReader(fd)
        barcodeset = {}
        barcodecount = 1
        for row in reader:
            barcodeset[row[barcodecol]]=(barcodecount,row[genecol])
            barcodecount += 1
        fd.close()
        if self.has_empty_vector_barcode:
            barcodeset[self.empty_vector_barcode_sequence.value]=(barcodecount,"EmptyVector")

        return barcodeset

    def likelihood(self,barcode,query):
        score=sum([self.matchscore(query[i],barcode[i]) for i in range(len(query))])
        return float(score/len(query))

    def queryall(self,barcodeset, query):
        matchscoredict={}
        barcodelist=barcodeset.keys()
        scoredict = {float(m)/(self.ncycles.value*2):[] for m in range((self.ncycles.value*2)+1)}
        [scoredict[self.likelihood(x,query)].append(x) for x in barcodelist]
        scores=scoredict.keys()
        scores.sort(reverse=True)
        matchcount = 1

        while matchcount <= self.number_matches.value:
            while len(scoredict[scores[0]]) == 0:
                scores = scores[1:]
            topscore = scoredict[scores[0]].pop(0)
            matchscoredict[matchcount] = (scores[0],topscore)
            matchcount += 1
        return matchscoredict

    def matchscore(self,querybase,truebase):
        halfmatch={"A":"C","C":"A","G":"T","T":"G"}
        if querybase==truebase:
            return 1
        elif querybase==halfmatch[truebase]:
            return 0.5
        else:
            return 0


    def get_measurement_columns(self, pipeline):
        input_object_name = self.input_object_name.value
        Nmatchdigits = len(str(self.number_matches.value))

        result = []

        result += [(cellprofiler.measurement.IMAGE,'_'.join([C_CALL_BARCODES,'ImageMeanQualityScore']), cellprofiler.measurement.COLTYPE_FLOAT)]

        result += [(input_object_name, '_'.join([C_CALL_BARCODES,'BarcodeCalled']), cellprofiler.measurement.COLTYPE_VARCHAR),
           (input_object_name, '_'.join([C_CALL_BARCODES,'MeanQualityScore']), cellprofiler.measurement.COLTYPE_FLOAT)]

        for eachcycle in range(1,self.ncycles.value+1):
            result += [(input_object_name, '_'.join([C_CALL_BARCODES,'Cycle'+str.zfill(str(eachcycle),2)+'QualityScore']), cellprofiler.measurement.COLTYPE_FLOAT)]

        for eachmatchN in range(1,self.number_matches.value+1):
            result += [(input_object_name,
                        '_'.join([C_CALL_BARCODES,'Match'+str.zfill(str(eachmatchN),Nmatchdigits)+'_Barcode']),
                        cellprofiler.measurement.COLTYPE_VARCHAR),
                    (input_object_name,
                     '_'.join([C_CALL_BARCODES,'Match'+str.zfill(str(eachmatchN),Nmatchdigits)+'_ID']),
                     cellprofiler.measurement.COLTYPE_INTEGER),
                    (input_object_name,
                     '_'.join([C_CALL_BARCODES,'Match'+str.zfill(str(eachmatchN),Nmatchdigits)+'_GeneCode']),
                     cellprofiler.measurement.COLTYPE_VARCHAR),
                    (input_object_name,
                     '_'.join([C_CALL_BARCODES,'Match'+str.zfill(str(eachmatchN),Nmatchdigits)+'_Score']),
                     cellprofiler.measurement.COLTYPE_FLOAT)]

        return result

    def get_categories(self, pipeline, object_name):
        if object_name == self.input_object_name or object_name == cellprofiler.measurement.IMAGE:
            return [C_CALL_BARCODES]

        return []

    def get_measurements(self, pipeline, object_name, category):
        Nmatchdigits = len(str(self.number_matches.value))

        if (object_name == self.input_object_name and category == C_CALL_BARCODES):
            result = ['BarcodeCalled','MeanQualityScore']

            for eachcycle in range(1,self.ncycles.value+1):
                result += ['Cycle'+str.zfill(str(eachcycle),2)+'QualityScore']

            for eachmatchN in range(1,self.number_matches.value+1):
                result += ['Match'+str.zfill(str(eachmatchN),Nmatchdigits)+'_Barcode', 'Match'+str.zfill(str(eachmatchN),Nmatchdigits)+'_ID',
                           'Match'+str.zfill(str(eachmatchN),Nmatchdigits)+'_GeneCode', 'Match'+str.zfill(str(eachmatchN),Nmatchdigits)+'_Score']

        elif object_name == object_name == cellprofiler.measurement.IMAGE:
            result = ['ImageMeanQualityScore']

        return result

        return []
