"""test_measuretrackquality.py: test the MeasureTrackQuality module

Copyright (c) 2017 University of Southern California

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions
of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED
TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.

Author: Dan Ruderman (ruderman@usc.edu)
"""

import unittest
import numpy

import measuretrackquality

# run in headless mode so wx is not required
import cellprofiler.preferences
cellprofiler.preferences.set_headless()

class test_MeasureTrackQuality(unittest.TestCase):
    def test_compute_typical_deviations(self):
        num_measurements = 10 # number of tests to run
        num_timepoints = 20
        num_cells = 10
        num_deviations_per_cell = num_timepoints-1
        num_deviations_per_measurement = num_cells * num_deviations_per_cell

        numpy.random.seed(17)
        target_medians = numpy.random.uniform(low=0.5, high=5, size=num_measurements) # results we expect

        def create_data_for_measurement(target_median):
            vals = numpy.abs(numpy.random.normal(size=num_deviations_per_measurement))
            abs_deviations = vals - numpy.median(vals) + target_median # enforce the desired median
            # make the deviations randomly positive or negative
            deviations = numpy.multiply(abs_deviations,
            numpy.random.choice([-1, 1], size=len(abs_deviations), replace=True))
            lists = [list(numpy.cumsum(numpy.insert(deviations[(cell*num_deviations_per_cell):((cell+1)*num_deviations_per_cell)],
                                                    0, numpy.random.normal()))) for cell in range(num_cells)]
            measurement_vals = sum(lists, []) # flatten
            return measurement_vals

        # create data set
        values_dict = {i : create_data_for_measurement(target_medians[i]) for i in range(num_measurements)}

        cell_ids = numpy.repeat(range(num_cells), num_timepoints)
        timepoints = numpy.tile(range(num_timepoints), num_cells)
        result_medians = measuretrackquality.MeasureTrackQuality.compute_typical_deviations(values_dict, cell_ids, timepoints)

        max_fractional_error = numpy.max(numpy.divide(numpy.abs(numpy.subtract(result_medians.values(), target_medians)), target_medians))

        self.assertLess(max_fractional_error, 1e-5, "Excessive error in compute_typical_deviations")

    def test_compute_tram(self):
        numpy.random.seed(17)
        num_timepoints = 50
        num_features = 5 # number of measurements to combine
        feature_names = [str(i) for i in range(num_features)]
        num_knots = num_timepoints / 5
        tram_exponent = 0.5

        # Make data with big DC offsets (which should be ignored by TrAM) and small variations. TrAM should be small.
        fluctuation_scale = 1
        offset_scale = 100*fluctuation_scale # huge offset which should be ignored by TrAM because of smoothing
        error_scale = 10*fluctuation_scale # big error relative to fluctuations which should be detected by TrAM

        # start with constant random constant data values
        base_data_array = numpy.repeat(numpy.random.normal(0, offset_scale, (1, num_features)), num_timepoints, 0)

        # add uncorrelated noise
        noise_array = numpy.random.normal(0, fluctuation_scale, (num_timepoints, num_features))
        data_1 = numpy.add(base_data_array, noise_array)

        tram_1 = measuretrackquality.MeasureTrackQuality.compute_TrAM(feature_names, data_1, range(num_timepoints),
                                                                      range(num_timepoints), num_knots, tram_exponent,
                                                                      [])

        # should be on the scale of the fluctuations
        self.assertLess(tram_1, 3*fluctuation_scale)

        # now add in a large sudden fluctuation which we should detect
        index = num_timepoints/2 # in the middle
        offset_array = numpy.zeros(data_1.shape)
        offset_array[index,:] = error_scale
        data_2 = numpy.add(data_1, offset_array)

        tram_2 = measuretrackquality.MeasureTrackQuality.compute_TrAM(feature_names, data_2, range(num_timepoints),
                                                                      range(num_timepoints), num_knots, tram_exponent,
                                                                      [])
        self.assertGreater(tram_2, error_scale/2) # should reflect the scale of the error

