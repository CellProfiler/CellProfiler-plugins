# coding=utf-8

"""
ConstrainObjects
================

**ConstrainObjects** removes portions of an object that exist beyond the boundaries
of a parent object. This assumes that the objects are related, i.e. have the
same object number. In order to achieve this, use a module like **RelateObjects**.

|

============ ============ ===============
Supports 2D? Supports 3D? Respects masks?
============ ============ ===============
NO           YES          NO
============ ============ ===============

"""

import numpy
import logging

import cellprofiler_core.image
import cellprofiler_core.object
import cellprofiler_core.module
import cellprofiler_core.setting
from cellprofiler_core.module.image_segmentation import ObjectProcessing
from cellprofiler_core.setting.choice import Choice
from cellprofiler_core.setting.subscriber import LabelSubscriber

log = logging.getLogger(__name__)

METHOD_IGNORE = "Ignore"
METHOD_REMOVE = "Remove protruding pieces"


class ConstrainObjects(ObjectProcessing):
    category = "Advanced"

    module_name = "ConstrainObjects"

    variable_revision_number = 1

    def create_settings(self):
        super(ConstrainObjects, self).create_settings()

        self.reference_name = LabelSubscriber(
            text="Constraining Objects",
            doc="Objects to use as reference for the constraint"
        )

        self.coersion_method = Choice(
            text="Handle protruding objects",
            choices=[METHOD_IGNORE, METHOD_REMOVE],
            value=METHOD_IGNORE,
            doc="""\
Assuming the objects are related, there may be some "child" objects
that protrude into the space of a "parent" object with a different label.
E.g. a nuclei from one cell may protrude into the membrane segmentation 
of a difference cell. This method sets how to handle these cases

**{METHOD_IGNORE}**: Ignore these protrusions, only constrain the real child
**{METHOD_REMOVE}**: Remove the portion of the child that protrudes into the wrong parent
""".format(**{
                "METHOD_IGNORE": METHOD_IGNORE,
                "METHOD_REMOVE": METHOD_REMOVE
            }
           )
        )

        self.remove_orphans = cellprofiler_core.setting.Binary(
            text="Remove children without a corresponding parent",
            value=False,
            doc="""
Some objects may be "parent-less" orphans, e.g. nuclei segmentations that have no 
corresponding, surrounding membrane segmentations. This specifies how to handle these
objects.

**{NO}**: Ignore them
**{YES}**: Remove the entire object from set
""".format(**{
                "YES": "Yes",
                "NO": "No"
            })
        )

    def settings(self):
        __settings__ = super(ConstrainObjects, self).settings()

        return __settings__ + [
            self.reference_name,
            self.coersion_method,
            self.remove_orphans
        ]

    def visible_settings(self):
        __settings__ = super(ConstrainObjects, self).visible_settings()

        __settings__ += [
            self.reference_name,
            self.coersion_method,
            self.remove_orphans
        ]

        return __settings__

    def run(self, workspace):
        x_name = self.x_name.value
        y_name = self.y_name.value
        object_set = workspace.object_set

        x = object_set.get_objects(x_name)
        x_data = x.segmented

        dimensions = x.dimensions
        y_data = x.segmented.copy()

        reference_name = self.reference_name.value
        reference = object_set.get_objects(reference_name)
        reference_data = reference.segmented

        # Get the parent object labels
        outer_labels = numpy.unique(reference_data)

        if self.remove_orphans.value:
            # Get the child object labels
            inner_labels = numpy.unique(x_data)
            # Find the discrepancies between child and parent
            orphans = numpy.setdiff1d(inner_labels, outer_labels)
            # Remove them from the original array
            orphan_mask = numpy.in1d(x_data, orphans)
            # orphan_mask here is a 1D array, but it has the same number of elements
            # as y_data. Since we know that, we can reshape it to the original array
            # shape and use it as a boolean mask to take out the orphaned objects
            y_data[orphan_mask.reshape(x_data.shape)] = 0

        for obj in outer_labels:
            # Ignore the background
            if obj == 0:
                continue

            # Find where in the array the child object is outside of the
            # parent object (i.e. where the original array is *not* that
            # object *and* where the child array is that object)
            constrain_mask = (reference_data != obj) & (x_data == obj)
            # Remove those parts outside the parent
            y_data[constrain_mask] = 0

            # Only remove intruding pieces if the user has requested it
            if self.coersion_method.value == METHOD_REMOVE:
                intrude_mask = (reference_data == obj) & (x_data != obj) & (x_data != 0)
                y_data[intrude_mask] = 0

        objects = cellprofiler_core.object.Objects()

        objects.segmented = y_data
        objects.parent_image = x.parent_image

        workspace.object_set.add_objects(objects, y_name)

        self.add_measurements(workspace)

        if self.show_window:
            workspace.display_data.x_data = x_data

            workspace.display_data.y_data = y_data

            workspace.display_data.reference = reference_data

            workspace.display_data.dimensions = dimensions

    def display(self, workspace, figure):
        layout = (2, 2)

        figure.set_subplots(
            dimensions=workspace.display_data.dimensions,
            subplots=layout
        )

        figure.subplot_imshow_labels(
            image=workspace.display_data.x_data,
            title=self.x_name.value,
            x=0,
            y=0
        )

        figure.subplot_imshow_labels(
            image=workspace.display_data.y_data,
            sharexy=figure.subplot(0, 0),
            title=self.y_name.value,
            x=1,
            y=0
        )

        figure.subplot_imshow_grayscale(
            image=workspace.display_data.reference,
            sharexy=figure.subplot(0, 0),
            title=self.reference_name.value,
            x=0,
            y=1
        )
