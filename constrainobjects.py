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

import cellprofiler.image
import cellprofiler.object
import cellprofiler.module
import cellprofiler.setting

log = logging.getLogger(__name__)

METHOD_MEDIAN = "Median Intensity"
METHOD_SUM = "Sum Intensity"
#
PEAK_SINGLE = "Accept Single Peak As Bottom"
PEAK_NAIVE = "Accept Only Two Peaks"
PEAK_APOSTERIORI = "Accept Nearest Peak After Highest Value"


class ConstrainObjects(cellprofiler.module.ObjectProcessing):
    category = "Advanced"

    module_name = "ConstrainObjects"

    variable_revision_number = 1

    def create_settings(self):
        super(ConstrainObjects, self).create_settings()

        self.reference_name = cellprofiler.setting.ObjectNameSubscriber(
            text="Constraining Objects",
            doc="Objects to use as reference for the constraint"
        )

        self.aggregation_method = cellprofiler.setting.Choice(
            text="Slice aggregation method",
            choices=[METHOD_MEDIAN, METHOD_SUM],
            value=METHOD_MEDIAN,
            doc="""\
Method by which XY slices are grouped to determine peak. 

**{METHOD_MEDIAN}**: Group by median intensity of each slice
**{METHOD_SUM}**: Group by sum intensity of each slice
""".format(**{
                "METHOD_MEDIAN": METHOD_MEDIAN,
                "METHOD_SUM": METHOD_SUM
            }
           )
        )

        self.top_padding = cellprofiler.setting.Integer(
            text="Top Padding",
            value=0,
            doc="Additional slices to keep beyond intensity peak"
        )

        self.bottom_padding = cellprofiler.setting.Integer(
            text="Bottom Padding",
            value=0,
            doc="Additional slices to keep beyond intensity peak"
        )

        self.use_gradient = cellprofiler.setting.Binary(
            text="Use gradient to choose peaks",
            value=False,
            doc="""
Use the gradient of the aggregation method (instead of the aggregation method itself) 
to determine clipping planes"""
        )

        self.use_moving_average = cellprofiler.setting.Binary(
            text="Apply a moving average to determine peaks",
            value=False,
            doc="""
Use a `moving average`_ (also called a "running mean") to smooth the curve
before calculating the peaks.

..  _moving average: https://en.wikipedia.org/wiki/Moving_average
"""
        )

        self.moving_average_size = cellprofiler.setting.Integer(
            text="Moving average window size",
            value=3,
            doc="""
Size of the window for moving average.
"""
        )

        self.peak_method = cellprofiler.setting.Choice(
            text="Peak Selection Method",
            choices=[PEAK_NAIVE, PEAK_SINGLE, PEAK_APOSTERIORI],
            value=PEAK_NAIVE,
            doc="""
Method for determining which peaks to choose for the clipping planes. 

*{PEAK_NAIVE}*: If the number of local maxima found is 2, accept those two as the 
peaks for the clipping planes. Otherwise, clip nothing.
*{PEAK_SINGLE}*: Same as *{PEAK_NAIVE}*, except if only one local maxima exists, 
that will be chosen as the bottom clipping plane (the top will not be clipped).
*{PEAK_APOSTERIORI}*: The maximum of the aggregate is chosen as the bottom clipping plane,
and the next closest peak when traveling "up" the z-stack is chosen as the top.
""".format(**{
                "PEAK_NAIVE": PEAK_NAIVE,
                "PEAK_SINGLE": PEAK_SINGLE,
                "PEAK_APOSTERIORI": PEAK_APOSTERIORI
            })
        )

    def settings(self):
        __settings__ = super(ConstrainObjects, self).settings()

        return __settings__ + [
            self.reference_name,
            self.aggregation_method,
            self.top_padding,
            self.bottom_padding,
            self.use_gradient,
            self.use_moving_average,
            self.moving_average_size,
            self.peak_method
        ]

    def visible_settings(self):
        __settings__ = super(ConstrainObjects, self).visible_settings()

        __settings__ += [
            self.reference_name,
            self.aggregation_method,
            self.top_padding,
            self.bottom_padding,
            self.use_gradient,
            self.use_moving_average
        ]

        if self.use_moving_average.value:
            __settings__ += [self.moving_average_size]

        return __settings__ + [self.peak_method]

    def run(self, workspace):
        x_name = self.x_name.value
        y_name = self.y_name.value
        object_set = workspace.object_set
        images = workspace.image_set

        x = object_set.get_objects(x_name)

        if not x.volumetric:
            raise NotImplementedError("This module is only compatible with 3D (volumetric) images, not 2D.")

        dimensions = x.dimensions
        y_data = x.segmented.copy()

        reference_name = self.reference_name.value
        reference = images.get_image(reference_name)
        reference_data = reference.pixel_data

        if self.aggregation_method.value == METHOD_MEDIAN:
            aggregation_method = numpy.median
        elif self.aggregation_method.value == METHOD_SUM:
            aggregation_method = numpy.sum
        else:
            raise ValueError("Invalid aggregation method selected")

        # Depending on aggregation method, the numbers can be quite large
        # Cast as float64 here to ensure that no overflow occurs
        z_aggregate = aggregation_method(reference_data, axis=(1, 2)).astype(numpy.float64)
        if self.use_gradient.value:
            z_aggregate = numpy.gradient(z_aggregate)

        # Depending on if the user requested a moving average, we may need to apply this
        # over the array
        # https://stackoverflow.com/a/22621523/3277713
        if self.use_moving_average.value:
            n = self.moving_average_size.value
            z_aggregate = numpy.convolve(z_aggregate, numpy.ones((n,)) / n, mode='same')

        # scipy-signal based local maxima
        if self.peak_method.value in [PEAK_SINGLE, PEAK_NAIVE]:
            # `argrelmax` always returns a tuple, but z_aggregate is one dimensional
            local_maxima = scipy.signal.argrelmax(z_aggregate)[0]
            num_maxima = len(local_maxima)

            if num_maxima == 1 and self.peak_method.value == PEAK_SINGLE:
                # Single peak accepted as bottom clipping plane
                # Don't clip off anything from the top
                local_maxima = [local_maxima[0], len(z_aggregate)]
            elif num_maxima != 2:
                log.warning("Unable to find only two maxima (found {}) - bypassing clipping operation".format(num_maxima))
                log.warning("Maxima found af the following indices: {}".format(local_maxima))
                local_maxima = [0, 0]

            # Apply padding based on user preference
            # Ensure the clipping plane isn't beyond the array's index
            bottom_slice = max(local_maxima[0] - self.bottom_padding.value, 0)
            top_slice = min(local_maxima[1] - self.top_padding.value, len(z_aggregate) - 1)

        # Aposteriori method
        else:
            # Find the bottom (e.g. maximum of aggregate)
            bottom_slice = numpy.argmax(z_aggregate)
            # Get the array from there on out
            upper_z_aggregate = z_aggregate[bottom_slice + 1:]
            # Find all the local maxima of the upper portion (see above for the indexing)
            local_maxima = scipy.signal.argrelmax(upper_z_aggregate)[0]
            # Get the first local extrema (if there are any)
            if not len(local_maxima):
                log.warning("Unable to find a second maximum after the first initial one - bypassing clipping operation")
                bottom_slice = 0
                top_slice = 0
            else:
                # Add the index of the bottom slice as offset
                top_slice = local_maxima[0] + bottom_slice

        # Apply to new object
        y_data[:bottom_slice, :, :] = 0
        # First check if top slice is zero, if so then we need to bypass
        if top_slice != 0:
            # We need to add 1 here to the top slice to _include_ the peak
            y_data[top_slice + 1:, :, :] = 0

        objects = cellprofiler.object.Objects()

        objects.segmented = y_data
        objects.parent_image = x.parent_image

        workspace.object_set.add_objects(objects, y_name)

        self.add_measurements(workspace)

        if self.show_window:
            workspace.display_data.x_data = x.segmented

            workspace.display_data.y_data = y_data

            workspace.display_data.reference = reference_data

            workspace.display_data.z_aggregate = z_aggregate

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

        figure.subplot_scatter(
            xvals=numpy.arange(len(workspace.display_data.z_aggregate)),
            yvals=workspace.display_data.z_aggregate,
            x=1,
            y=1,
            title=self.aggregation_method.value
        )
