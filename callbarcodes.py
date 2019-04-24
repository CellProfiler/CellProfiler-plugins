# coding=utf-8

#################################
#
# Imports from useful Python libraries
#
#################################

import numpy
import os

#################################
#
# Imports from CellProfiler
#
##################################

import cellprofiler.image
import cellprofiler.module
import cellprofiler.measurement
import cellprofiler.object
import cellprofiler.setting
from cellprofiler.modules.loaddata import open_csv, get_header


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

Are there any assumptions about input data someone using this module
should be made aware of? For example, is there a strict requirement that
image data be single-channel, or that the foreground is brighter than
the background? Describe any assumptions here.

This section can be omitted if there is no requirement on the input.

What do I get as output?
^^^^^^^^^^^^^^^^^^^^^^^^

Describe the output of this module. This is necessary if the output is
more complex than a single image. For example, if there is data displayed
over the image then describe what the data represents.

This section can be omitted if there is no specialized output.

Measurements made by this module
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Describe the measurements made by this module. Typically, measurements
are described in the following format:

**Measurement category:**

-  *MeasurementName*: A brief description of the measurement.
-  *MeasurementName*: A brief description of the measurement.

**Measurement category:**

-  *MeasurementName*: A brief description of the measurement.
-  *MeasurementName*: A brief description of the measurement.

This module makes the following measurements:

**MT** (the MeasurementTemplate category):

-  *Intensity_[IMAGE_NAME]_N[Ni]_M[Mj]*: the Zernike feature of the
   IMAGE_NAME image with radial degree Ni and Azimuthal degree Mj,
   Mj >= 0.
-  *Intensity_[IMAGE_NAME]_N[Ni]_MM[Mj]*: the Zernike feature of
   the IMAGE_NAME image with radial degree Ni and Azimuthal degree
   Mj, Mj < 0.

Technical notes
^^^^^^^^^^^^^^^

Include implementation details or notes here. Additionally provide any 
other background information about this module, including definitions
or adopted conventions. Information which may be too specific to fit into
the general description should be provided here.

Omit this section if there is no technical information to mention.

The Zernike features measured here are themselves interesting. You can 
reconstruct the image of a cell, approximately, by constructing the Zernike 
functions on a unit circle, multiplying the real parts by the corresponding 
features for positive M, multiplying the imaginary parts by the corresponding 
features for negative M and adding real and imaginary parts.

References
^^^^^^^^^^

Provide citations here, if appropriate. Citations are formatted as a list and,
wherever possible, include a link to the original work. For example,

-  Meyer F, Beucher S (1990) “Morphological segmentation.” *J Visual
   Communication and Image Representation* 1, 21-46.
   (`link <http://dx.doi.org/10.1016/1047-3203(90)90014-M>`__)
"""

#
# Constants
#
# It's good programming practice to replace things like strings with
# constants if they will appear more than once in your program. That way,
# if someone wants to change the text, that text will change everywhere.
# Also, you can't misspell it by accident.
#
'''This is the measurement template category'''
C_CALL_BARCODES = "Barcode"


#
# The module class
#
# Your module should "inherit" from cellprofiler.module.Module.
# This means that your module will use the methods from Module unless
# you re-implement them. You can let Module do most of the work and
# implement only what you need.
#
class CallBarcodes(cellprofiler.module.Module):
    #
    # The module starts by declaring the name that's used for display,
    # the category under which it is stored and the variable revision
    # number which can be used to provide backwards compatibility if
    # you add user-interface functionality later.
    #
    module_name = "CallBarcodes"
    category = "Measurement"
    variable_revision_number = 1

    #
    # "create_settings" is where you declare the user interface elements
    # (the "settings") which the user will use to customize your module.
    #
    # You can look at other modules and in cellprofiler.settings for
    # settings you can use.
    #
    def create_settings(self):
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
            exts=[("Data file (*.csv)", "*.csv"), ("All files (*.*)", "*.*")]

        #
        # The ObjectNameSubscriber is similar to the ImageNameSubscriber.
        # It will ask the user which object to pick from the list of
        # objects provided by upstream modules.
        #
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

    #
    # The "settings" method tells CellProfiler about the settings you
    # have in your module. CellProfiler uses the list for saving
    # and restoring values for your module when it saves or loads a
    # pipeline file.
    #
    # This module does not have a "visible_settings" method. CellProfiler
    # will use "settings" to make the list of user-interface elements
    # that let the user configure the module. See imagetemplate.py for
    # a template for visible_settings that you can cut and paste here.
    #
    def settings(self):
        return [
            self.input_image_name,
            self.input_object_name,
            self.radial_degree
        ]

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
                self.csv_file_name

    @property
    def csv_path(self):
        '''The path and file name of the CSV file to be loaded'''
        if cellprofiler.preferences.get_data_file() is not None:
            return cellprofiler.preferences.get_data_file()
        if self.csv_directory.dir_choice == cellprofiler.setting.URL_FOLDER_NAME:
            return self.csv_file_name.value

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


    #
    # CellProfiler calls "run" on each image set in your pipeline.
    #
    def run(self, workspace):
        #
        # Get the measurements object - we put the measurements we
        # make in here
        #
        measurements = workspace.measurements

        #
        # We record some statistics which we will display later.
        # We format them so that Matplotlib can display them in a table.
        # The first row is a header that tells what the fields are.
        #
        statistics = [["Feature", "Mean", "Median", "SD"]]

        #
        # Put the statistics in the workspace display data so we
        # can get at them when we display
        #
        workspace.display_data.statistics = statistics

        #
        # Get the input image and object. You need to get the .value
        # because otherwise you'll get the setting object instead of
        # the string name.
        #
        input_object_name = self.input_object_name.value

        ################################################################
        #
        # GETTING AN IMAGE FROM THE IMAGE SET
        #
        # Get the image set. The image set has all of the images in it.
        #
        image_set = workspace.image_set
        #

        ###############################################################

        ###############################################################
        #
        # GETTING THE LABELS MATRIX FROM THE OBJECT SET
        #
        # The object set has all of the objects in it.
        #
        object_set = workspace.object_set

        ###############################################################

        #
        # The minimum enclosing circle (MEC) is the smallest circle that
        # will fit around the object. We get the centers and radii of
        # all of the objects at once. You'll see how that lets us
        # compute the X and Y position of each pixel in a label all at
        # one go.
        #
        # First, get an array that lists the whole range of indexes in
        # the labels matrix.
        #
        indexes = objects.indices
        #
        # The module computes a measurement based on the image intensity
        # inside an object times a Zernike polynomial inscribed in the
        # minimum enclosing circle around the object. The details are
        # in the "measure_zernike" function. We call into the function with
        # an N and M which describe the polynomial.
        #
        for n, m in self.get_zernike_indexes():
            # Compute the zernikes for each object, returned in an array
            zr, zi = self.measure_zernike(pixels, labels, indexes, centers, radius, n, m)

            # Get the name of the measurement feature for this zernike
            feature = self.get_measurement_name(n, m)

            # Add a measurement for this kind of object
            if m != 0:
                measurements.add_measurement(input_object_name, feature, zr)

                # Do the same with -m
                feature = self.get_measurement_name(n, -m)
                measurements.add_measurement(input_object_name, feature, zi)
            else:
                # For zero, the total is the sum of real and imaginary parts
                measurements.add_measurement(input_object_name, feature, zr + zi)

            # Record the statistics.
            zmean = numpy.mean(zr)
            zmedian = numpy.median(zr)
            zsd = numpy.std(zr)
            statistics.append([feature, zmean, zmedian, zsd])

    #
    # "display" lets you use matplotlib to display your results.
    #
    def display(self, workspace, figure):
        statistics = workspace.display_data.statistics

        figure.set_subplots((1, 1))

        figure.subplot_table(0, 0, statistics)



    def likelihood(self,barcode,query):
        score=0
        halfmatch={"A":"C","C":"A","G":"T","T":"G"}
        for i in range(len(query)):
            if query[i]==barcode[i]:
                score+=1
            elif halfmatch[query[i]]==barcode[i]:
                score+=0.5
        return score/len(query)

    def queryall(self,barcodelist, query):
        scoredict={likelihood(x,query):x for x in barcodelist}
        scores=scoredict.keys()
        scores.sort(reverse=True)
        return scores[0],scoredict[scores[0]]



    #
    # Here, we go about naming the measurements.
    #
    # Measurement names have parts to them, separated by underbars.
    # There's always a category and a feature name
    # and sometimes there are modifiers such as the image that
    # was measured or the scale at which it was measured.
    #
    # We have functions that build the names so that we can
    # use the same functions in different places.
    #
    def get_feature_name(self, n, m):
        '''Return a measurement feature name for the given Zernike'''
        #
        # Something nice and simple for a name... Intensity_DNA_N4M2 for instance
        #
        if m >= 0:
            return "Intensity_%s_N%dM%d" % (self.input_image_name.value, n, m)

        return "Intensity_%s_N%dMM%d" % (self.input_image_name.value, n, -m)

    def get_measurement_name(self, n, m):
        '''Return the whole measurement name'''
        input_image_name = self.input_image_name.value

        return '_'.join([C_MEASUREMENT_TEMPLATE, self.get_feature_name(n, m)])

    #
    # We have to tell CellProfiler about the measurements we produce.
    # There are two parts: one that is for database-type modules and one
    # that is for the UI. The first part gives a comprehensive list
    # of measurement columns produced. The second is more informal and
    # tells CellProfiler how to categorize its measurements.
    #
    # "get_measurement_columns" gets the measurements for use in the database
    # or in a spreadsheet. Some modules need this because they
    # might make measurements of measurements and need those names.
    #
    def get_measurement_columns(self, pipeline):
        #
        # We use a list comprehension here.
        # See http://docs.python.org/tutorial/datastructures.html#list-comprehensions
        # for how this works.
        #
        # The first thing in the list is the object being measured. If it's
        # the whole image, use cellprofiler.measurement.IMAGE as the name.
        #
        # The second thing is the measurement name.
        #
        # The third thing is the column type. See the COLTYPE constants
        # in measurement.py for what you can use
        #
        input_object_name = self.input_object_name.value

        return [(
            input_object_name,
            self.get_measurement_name(n, m),
            cellprofiler.measurement.COLTYPE_FLOAT
        ) for n, m in self.get_zernike_indexes(True)]

    #
    # "get_categories" returns a list of the measurement categories produced
    # by this module. It takes an object name - only return categories
    # if the name matches.
    #
    def get_categories(self, pipeline, object_name):
        if object_name == self.input_object_name:
            return [C_MEASUREMENT_TEMPLATE]

        return []

    #
    # Return the feature names if the object_name and category match
    #
    def get_measurements(self, pipeline, object_name, category):
        if (object_name == self.input_object_name and category == C_MEASUREMENT_TEMPLATE):
            return ["Intensity"]

        return []

    #
    # This module makes per-image measurements. That means we need
    # "get_measurement_images" to distinguish measurements made on two
    # different images by this module
    #
    def get_measurement_images(self, pipeline, object_name, category, measurement):
        #
        # This might seem wasteful, but UI code can be slow. Just see
        # if the measurement is in the list returned by get_measurements
        #
        if measurement in self.get_measurements(pipeline, object_name, category):
            return [self.input_image_name.value]

        return []

    def get_measurement_scales(self, pipeline, object_name, category, measurement, image_name):
        '''Get the scales for a measurement

        For the Zernikes, the scales are of the form, N2M2 or N2MM2 for
        negative azimuthal degree
        '''
        def get_scale(n, m):
            if m >= 0:
                return "N%dM%d" % (n, m)

            return "N%dMM%d" % (n, -m)

        if image_name in self.get_measurement_images(pipeline, object_name, category, measurement):
            return [get_scale(n, m) for n, m in self.get_zernike_indexes(True)]

        return []

    @staticmethod
    def get_image_from_features(radius, feature_dictionary):
        '''Reconstruct the intensity image from the zernike features

        radius - the radius of the minimum enclosing circle

        feature_dictionary - keys are (n, m) tuples and values are the
        magnitudes.

        returns a greyscale image based on the feature dictionary.
        '''
        i, j = numpy.mgrid[-radius:(radius + 1), -radius:(radius + 1)].astype(float) / radius
        mask = (i * i + j * j) <= 1

        zernike_indexes = numpy.array(feature_dictionary.keys())
        zernike_features = numpy.array(feature_dictionary.values())

        z = centrosome.zernike.construct_zernike_polynomials(j, i, numpy.abs(zernike_indexes), mask=mask)
        zn = (2 * zernike_indexes[:, 0] + 2) / ((zernike_indexes[:, 1] == 0) + 1) / numpy.pi
        z *= zn[numpy.newaxis, numpy.newaxis, :]
        z = z.real * (zernike_indexes[:, 1] >= 0)[numpy.newaxis, numpy.newaxis, :] + \
            z.imag * (zernike_indexes[:, 1] <= 0)[numpy.newaxis, numpy.newaxis, :]

        return numpy.sum(z * zernike_features[numpy.newaxis, numpy.newaxis, :], 2)
