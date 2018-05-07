import numpy
import numpy.testing
import skimage.morphology
import skimage.segmentation
import pytest
import scipy.ndimage
import skimage.filters
import skimage.feature

import seedobjects


instance = seedobjects.SeedObjects()


@pytest.fixture(scope="module")
def image_labels():
    labels = numpy.zeros((20, 20), dtype=numpy.uint8)

    labels[2:8, 2:8] = 1

    labels[0:8, 12:18] = 2

    labels[12:18, 0:8] = 3

    labels[12:20, 12:20] = 4

    return labels


@pytest.fixture(scope="module")
def volume_labels():
    labels = numpy.zeros((9, 20, 20), dtype=numpy.uint8)

    labels[0:9, 2:8, 2:8] = 1

    labels[0:5, 0:8, 12:18] = 2

    labels[4:9, 12:18, 0:8] = 3

    labels[1:8, 12:20, 12:20] = 4

    return labels


@pytest.fixture(
    scope="module", 
    params=[False, True],
    ids=["keep_lonely", "remove_lonely"])
def remove_below(request):
    return request.param


def test_run(object_set_with_data, module, workspace_with_data, remove_below):
    input_objs = object_set_with_data.get_objects("InputObjects").segmented

    im_dim = input_objs.ndim

    if im_dim == 2:
        strel = "disk,2"
    else:
        strel = "ball,2"

    module.x_name.value = "InputObjects"
    module.y_name.value = "OutputObjects"
    module.structuring_element.value = strel

    module.run(workspace_with_data)

    actual = workspace_with_data.object_set.get_objects("OutputObjects").segmented

    seeds = scipy.ndimage.distance_transform_edt(input_objs)

    seeds = skimage.filters.gaussian(seeds, sigma=1)

    seeds = skimage.feature.peak_local_max(seeds,
                                           min_distance=1,
                                           threshold_rel=0,
                                           exclude_border=False,
                                           num_peaks=numpy.inf,
                                           indices=False)

    expected = skimage.morphology.binary_dilation(seeds, module.structuring_element.value)

    numpy.testing.assert_array_equal(actual, expected)

#
# def test_2d_merge_objects(image_labels, module, object_set_empty, objects_empty, workspace_empty):
#     labels = image_labels.copy()
#     labels[5, 5] = 5
#     labels[2, 15] = 6
#     labels[15, 2] = 7
#     labels[15, 15] = 8
#
#     objects_empty.segmented = labels
#
#     module.x_name.value = "InputObjects"
#     module.y_name.value = "OutputObjects"
#     module.size.value = 2.
#
#     module.run(workspace_empty)
#
#     actual = object_set_empty.get_objects("OutputObjects").segmented
#     expected = image_labels
#
#     numpy.testing.assert_array_equal(actual, expected)
#
#
# def test_3d_fill_holes(volume_labels, module, object_set_empty, objects_empty, workspace_empty):
#     labels = volume_labels.copy()
#     labels[5, 5, 5] = 5
#     labels[2, 2, 15] = 6
#     labels[5, 15, 2] = 7
#     labels[5, 15, 15] = 8
#
#     objects_empty.segmented = labels
#
#     module.x_name.value = "InputObjects"
#     module.y_name.value = "OutputObjects"
#     module.size.value = 2.
#
#     module.run(workspace_empty)
#
#     actual = object_set_empty.get_objects("OutputObjects").segmented
#     expected = volume_labels
#
#     numpy.testing.assert_array_equal(actual, expected)
#
#
# def test_fail_3d_merge_large_object(volume_labels, module, object_set_empty, objects_empty, workspace_empty):
#     labels = volume_labels.copy()
#     # Create a 'large' object
#     labels[5:10, 4:6, 4:6] = 5
#
#     objects_empty.segmented = labels
#
#     module.x_name.value = "InputObjects"
#     module.y_name.value = "OutputObjects"
#     # Set size below minimum
#     module.size.value = 3.
#
#     module.run(workspace_empty)
#
#     actual = object_set_empty.get_objects("OutputObjects").segmented
#     expected = labels
#
#     # Since the 3D size is above the minimum size threshold, no object should be merged
#     numpy.testing.assert_array_equal(actual, expected)
#
#
# def test_pass_3d_merge_large_object(volume_labels, module, object_set_empty, objects_empty, workspace_empty):
#     labels = volume_labels.copy()
#     # Create a 'large' object
#     labels[5:10, 4:6, 4:6] = 5
#
#     objects_empty.segmented = labels
#
#     module.x_name.value = "InputObjects"
#     module.y_name.value = "OutputObjects"
#     # Set size below minimum
#     module.size.value = 3.
#     # Set to slicewise so the 'large' object is merged at each slice
#     module.slice_wise.value = True
#
#     module.run(workspace_empty)
#
#     actual = object_set_empty.get_objects("OutputObjects").segmented
#     expected = volume_labels
#
#     # We're filling slice-wise here, so each 2D slice should have the object merged
#     numpy.testing.assert_array_equal(actual, expected)
#
#
# def test_2d_keep_nonneighbored_objects(image_labels, module, object_set_empty, objects_empty, workspace_empty):
#     labels = image_labels.copy()
#     # Create "small"
#     labels[8:12, 9:11] = 8
#
#     objects_empty.segmented = labels
#
#     module.x_name.value = "InputObjects"
#     module.y_name.value = "OutputObjects"
#     module.size.value = 4.
#     # Modify threshold removal procedure
#     module.remove_below_threshold.value = False
#
#     module.run(workspace_empty)
#
#     actual = object_set_empty.get_objects("OutputObjects").segmented
#     # Object with no neighbors should not be removed
#     expected = labels
#
#     numpy.testing.assert_array_equal(actual, expected)
#
#
# def test_3d_keep_nonneighbored_object(volume_labels, module, object_set_empty, objects_empty, workspace_empty):
#     labels = volume_labels.copy()
#     labels[8:12, 9:11, 4:6] = 8
#
#     objects_empty.segmented = labels
#
#     module.x_name.value = "InputObjects"
#     module.y_name.value = "OutputObjects"
#     module.size.value = 4.
#     # Modify threshold removal procedure
#     module.remove_below_threshold.value = False
#
#     module.run(workspace_empty)
#
#     actual = object_set_empty.get_objects("OutputObjects").segmented
#     # Object with no neighbors should not be removed
#     expected = labels
#
#     numpy.testing.assert_array_equal(actual, expected)
