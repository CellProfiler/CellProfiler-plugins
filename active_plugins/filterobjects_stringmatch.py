from cellprofiler_core.module.image_segmentation import ObjectProcessing
from cellprofiler_core.setting import (
    Divider,
)
from cellprofiler_core.setting.text import Alphanumeric
from cellprofiler_core.setting.choice import Choice

__doc__ = ""

import logging
import os

import numpy
import scipy
import scipy.ndimage
import scipy.sparse

import cellprofiler_core.object
from cellprofiler.utilities.rules import Rules

LOGGER = logging.getLogger(__name__)

METHOD_EXACT = "Exact match"
METHOD_CONTAINS = "String contains"

class FilterObjects_StringMatch(ObjectProcessing):
    module_name = "FilterObjects_StringMatch"

    variable_revision_number = 1

    def __init__(self):
        self.rules = Rules()

        super(FilterObjects_StringMatch, self).__init__()

    def create_settings(self):
        super(FilterObjects_StringMatch, self).create_settings()

        self.x_name.text = """Select the objects to filter"""

        self.x_name.doc = ""

        self.y_name.text = """Name the output objects"""

        self.y_name.doc = "Enter a name for the collection of objects that are retained after applying the filter(s)."

        self.spacer_1 = Divider(line=False)

        self.filter_out = Alphanumeric(
            "What string to filter out",
            "AAAA",
            doc="""Enter the string that should be used to filter objects.""",
        )

        self.filter_method = Choice(
            "Filter method",
            [METHOD_EXACT, METHOD_CONTAINS],
            doc="""Select whether to only filter objects that are an exact match for the string entered
            (e.g. Object 'AAAAB' will NOT be filtered by string 'AAAA') 
             or to filter any object that contains the string entered
             (e.g. Object 'AAAAB' will be filtered by string 'AAAA').""",
        )

        #self.filter_column = 

        self.rules.create_settings()

    def settings(self):
        settings = super(FilterObjects_StringMatch, self).settings()
        settings += [self.filter_out,self.filter_method]
        return settings

    def visible_settings(self):
        visible_settings = super(FilterObjects_StringMatch, self).visible_settings()
        visible_settings += [
                self.filter_out,
                self.filter_method
            ]
        return visible_settings              

    def run(self, workspace):
        """Filter objects for this image set, display results"""
        src_objects = workspace.get_objects(self.x_name.value)
        
        indexes = self.keep_by_string(workspace, src_objects)

        #
        # Create an array that maps label indexes to their new values
        # All labels to be deleted have a value in this array of zero
        #
        new_object_count = len(indexes)
        max_label = numpy.max(src_objects.segmented)
        label_indexes = numpy.zeros((max_label + 1,), int)
        label_indexes[indexes] = numpy.arange(1, new_object_count + 1)
        #
        # Loop over both the primary and additional objects
        #
        object_list = [(self.x_name.value, self.y_name.value)]
        m = workspace.measurements
        first_set = True
        for src_name, target_name in object_list:
            src_objects = workspace.get_objects(src_name)
            target_labels = src_objects.segmented.copy()
            #
            # Reindex the labels of the old source image
            #
            target_labels[target_labels > max_label] = 0
            target_labels = label_indexes[target_labels]
            #
            # Make a new set of objects - retain the old set's unedited
            # segmentation for the new and generally try to copy stuff
            # from the old to the new.
            #
            target_objects = cellprofiler_core.object.Objects()
            target_objects.segmented = target_labels
            target_objects.unedited_segmented = src_objects.unedited_segmented
            #
            # Remove the filtered objects from the small_removed_segmented
            # if present. "small_removed_segmented" should really be
            # "filtered_removed_segmented".
            #
            small_removed = src_objects.small_removed_segmented.copy()
            small_removed[(target_labels == 0) & (src_objects.segmented != 0)] = 0
            target_objects.small_removed_segmented = small_removed
            if src_objects.has_parent_image:
                target_objects.parent_image = src_objects.parent_image
            workspace.object_set.add_objects(target_objects, target_name)

            self.add_measurements(workspace, src_name, target_name)
            if self.show_window and first_set:
                workspace.display_data.src_objects_segmented = src_objects.segmented
                workspace.display_data.target_objects_segmented = target_objects.segmented
                workspace.display_data.dimensions = src_objects.dimensions
                first_set = False

    def display(self, workspace, figure):
        """Display what was filtered"""
        src_name = self.x_name.value
        src_objects_segmented = workspace.display_data.src_objects_segmented
        target_objects_segmented = workspace.display_data.target_objects_segmented
        dimensions = workspace.display_data.dimensions

        target_name = self.y_name.value

        figure.set_subplots((2, 2), dimensions=dimensions)

        figure.subplot_imshow_labels(
            0, 0, src_objects_segmented, title="Original: %s" % src_name
        )

        figure.subplot_imshow_labels(
            1,
            0,
            target_objects_segmented,
            title="Filtered: %s" % target_name,
            sharexy=figure.subplot(0, 0),
        )

        pre = numpy.max(src_objects_segmented)
        post = numpy.max(target_objects_segmented)

        statistics = [[pre], [post], [pre - post]]

        figure.subplot_table(
            0,
            1,
            statistics,
            row_labels=(
                "Number of objects pre-filtering",
                "Number of objects post-filtering",
                "Number of objects removed",
            ),
        )

    def keep_by_string(self, workspace, src_objects):
        """
        workspace - workspace passed into Run
        src_objects - the Objects instance to be filtered
        """
        src_name = self.x_name.value
        m = workspace.measurements
        values = m.get_current_measurement(src_name, "Barcode_BarcodeCalled")
        if self.filter_method == METHOD_EXACT:
            # Is this structure still necessary or is it an artifact?
            # Could be just values == self.filter_out.value
            # Make an array of True
            hits = numpy.ones(len(values), bool)
            # Fill with False for those where we want to filter out
            hits[values == self.filter_out.value] = False
        elif self.filter_method == METHOD_CONTAINS:
            hits = [self.filter_out.value in x for x in values]
        # Get object numbers for things that are True
        indexes = numpy.argwhere(hits)[:, 0]
        # Objects are 1 counted, Python is 0 counted
        indexes = indexes + 1

        return indexes
