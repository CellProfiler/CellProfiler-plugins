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

    labels[2:9, 2:9] = 1

    labels[0:9, 12:19] = 2

    labels[12:19, 0:9] = 3

    labels[14:21, 14:21] = 4

    return labels


@pytest.fixture(scope="module")
def volume_labels():
    labels = numpy.zeros((9, 20, 20), dtype=numpy.uint8)

    labels[0:9, 2:9, 2:9] = 1

    labels[0:5, 0:9, 12:19] = 2

    labels[4:11, 12:19, 0:9] = 3

    labels[1:10, 14:21, 14:21] = 4

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


def test_2d_regular(image_labels, module, object_set_empty, objects_empty, workspace_empty):
    labels = numpy.zeros_like(image_labels)
    labels[5, 5] = 1
    labels[4, 15] = 1
    labels[15, 4] = 1
    labels[17, 17] = 1

    objects_empty.segmented = image_labels

    module.x_name.value = "InputObjects"
    module.y_name.value = "OutputObjects"
    module.structuring_element.value = "disk,0"

    module.run(workspace_empty)

    actual = object_set_empty.get_objects("OutputObjects").segmented
    expected = labels

    numpy.testing.assert_array_equal(actual, expected)


def test_3d_regular(volume_labels, module, object_set_empty, objects_empty, workspace_empty):
    labels = numpy.zeros_like(volume_labels)

    labels[4, 5, 5] = 1
    labels[2, 4, 15] = 1
    labels[6, 15, 4] = 1
    labels[5, 17, 17] = 1

    objects_empty.segmented = volume_labels

    module.x_name.value = "InputObjects"
    module.y_name.value = "OutputObjects"
    module.structuring_element.value = "ball,0"

    module.run(workspace_empty)

    actual = object_set_empty.get_objects("OutputObjects").segmented
    expected = labels

    numpy.testing.assert_array_equal(actual, expected)


def test_2d_min_dist(image_labels, module, object_set_empty, objects_empty, workspace_empty):
    labels = numpy.zeros_like(image_labels)
    labels[4, 15] = 1
    labels[15, 4] = 1

    objects_empty.segmented = image_labels

    module.x_name.value = "InputObjects"
    module.y_name.value = "OutputObjects"
    module.structuring_element.value = "disk,0"

    module.min_dist.value = 12

    module.run(workspace_empty)

    actual = object_set_empty.get_objects("OutputObjects").segmented
    expected = labels

    numpy.testing.assert_array_equal(actual, expected)


def test_3d_min_dist(volume_labels, module, object_set_empty, objects_empty, workspace_empty):
    labels = numpy.zeros_like(volume_labels)

    labels[2, 4, 15] = 1
    labels[7, 15, 4] = 1

    objects_empty.segmented = labels

    module.x_name.value = "InputObjects"
    module.y_name.value = "OutputObjects"
    module.structuring_element.value = "ball,0"

    module.min_dist.value = 64

    module.run(workspace_empty)

    actual = object_set_empty.get_objects("OutputObjects").segmented
    expected = labels

    numpy.testing.assert_array_equal(actual, expected)
