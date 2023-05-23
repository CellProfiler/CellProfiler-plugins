import numpy
import numpy.testing
import skimage.morphology
import skimage.segmentation
import pytest
import scipy.ndimage
import skimage.filters
import skimage.feature
import skimage.util

import seedobjects


instance = seedobjects.SeedObjects


@pytest.fixture(scope="module")
def image_labels():
    labels = numpy.zeros((20, 20), dtype=numpy.uint8)

    # Midpoint - 5, 5
    # Size = 7x7 (49)
    labels[2:9, 2:9] = 1

    # Midpoint - 4, 15
    # Size = 9x7 (63)
    labels[0:9, 12:19] = 2

    # Midpoint - 15, 4
    # Size = 7x9 (63)
    labels[12:19, 0:9] = 3

    # Midpoint - 17, 17
    # Size = 7x7 (49)
    labels[14:21, 14:21] = 4

    return labels


@pytest.fixture(scope="module")
def volume_labels():
    labels = numpy.zeros((9, 20, 20), dtype=numpy.uint8)

    # Midpoint - 4, 5, 5
    # Size = 9x7x7 (441)
    labels[0:9, 2:9, 2:9] = 1

    # Midpoint - 2, 4, 15
    # Size = 5x9x7 (315)
    labels[0:5, 0:9, 12:19] = 2

    # Midpoint - 6, 15, 4
    # Size = 7x9x7 (441)
    labels[4:11, 12:19, 0:9] = 3

    # Midpoint - 5, 17, 17
    # Size = 9x7x7 (441)
    labels[1:10, 14:21, 14:21] = 4

    return labels


def test_run(object_set_with_data, module, workspace_with_data):
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

    padded = skimage.util.pad(input_objs, 1, mode='constant', constant_values=0)

    seeds = scipy.ndimage.distance_transform_edt(padded)

    seeds = skimage.util.crop(seeds, 1)

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


def test_2d_min_intensity(image_labels, module, object_set_empty, objects_empty, workspace_empty):
    labels = numpy.zeros_like(image_labels)

    # Only the largest objects should be seeded
    labels[4, 15] = 1
    labels[15, 4] = 1

    objects_empty.segmented = image_labels

    module.x_name.value = "InputObjects"
    module.y_name.value = "OutputObjects"
    module.structuring_element.value = "disk,0"

    module.min_intensity.value = 0.95

    module.run(workspace_empty)

    actual = object_set_empty.get_objects("OutputObjects").segmented
    expected = labels

    numpy.testing.assert_array_equal(actual, expected)


def test_3d_min_intensity(volume_labels, module, object_set_empty, objects_empty, workspace_empty):
    labels = numpy.zeros_like(volume_labels)

    labels[4, 5, 5] = 1
    labels[5, 17, 17] = 1

    objects_empty.segmented = volume_labels

    module.x_name.value = "InputObjects"
    module.y_name.value = "OutputObjects"
    module.structuring_element.value = "ball,0"

    module.min_intensity.value = 0.77

    module.run(workspace_empty)

    actual = object_set_empty.get_objects("OutputObjects").segmented
    expected = labels

    numpy.testing.assert_array_equal(actual, expected)


def test_2d_border_exclude(image_labels, module, object_set_empty, objects_empty, workspace_empty):
    labels = numpy.zeros_like(image_labels)

    labels[5, 5] = 1

    objects_empty.segmented = image_labels

    module.x_name.value = "InputObjects"
    module.y_name.value = "OutputObjects"
    module.structuring_element.value = "disk,0"

    module.exclude_border.value = 5

    module.run(workspace_empty)

    actual = object_set_empty.get_objects("OutputObjects").segmented
    expected = labels

    numpy.testing.assert_array_equal(actual, expected)


def test_3d_border_exclude(volume_labels, module, object_set_empty, objects_empty, workspace_empty):
    labels = numpy.zeros_like(volume_labels)

    labels[4, 5, 5] = 1

    objects_empty.segmented = volume_labels

    module.x_name.value = "InputObjects"
    module.y_name.value = "OutputObjects"
    module.structuring_element.value = "ball,0"

    module.exclude_border.value = 3

    module.run(workspace_empty)

    actual = object_set_empty.get_objects("OutputObjects").segmented
    expected = labels

    numpy.testing.assert_array_equal(actual, expected)


def test_2d_max_seeds(image_labels, module, object_set_empty, objects_empty, workspace_empty):
    labels = numpy.zeros_like(image_labels)

    labels[4, 15] = 1
    labels[15, 4] = 1

    objects_empty.segmented = image_labels

    module.x_name.value = "InputObjects"
    module.y_name.value = "OutputObjects"
    module.structuring_element.value = "disk,0"

    module.max_seeds.value = 2

    module.run(workspace_empty)

    actual = object_set_empty.get_objects("OutputObjects").segmented
    expected = labels

    numpy.testing.assert_array_equal(actual, expected)


def test_3d_max_seeds(volume_labels, module, object_set_empty, objects_empty, workspace_empty):
    labels = numpy.zeros_like(volume_labels)

    labels[4, 5, 5] = 1
    labels[5, 17, 17] = 1

    objects_empty.segmented = volume_labels

    module.x_name.value = "InputObjects"
    module.y_name.value = "OutputObjects"
    module.structuring_element.value = "ball,0"

    module.max_seeds.value = 2

    module.run(workspace_empty)

    actual = object_set_empty.get_objects("OutputObjects").segmented
    expected = labels

    numpy.testing.assert_array_equal(actual, expected)


def test_2d_strel(image_labels, module, object_set_empty, objects_empty, workspace_empty):
    labels = numpy.zeros_like(image_labels)
    labels[5, 5] = 1
    labels[4, 15] = 1
    labels[15, 4] = 1
    labels[17, 17] = 1

    objects_empty.segmented = image_labels

    module.x_name.value = "InputObjects"
    module.y_name.value = "OutputObjects"
    module.structuring_element.value = "disk,2"

    module.run(workspace_empty)

    actual = object_set_empty.get_objects("OutputObjects").segmented

    labels = skimage.morphology.binary_dilation(labels, skimage.morphology.disk(2))

    expected = labels

    numpy.testing.assert_array_equal(actual, expected)


def test_3d_strel(volume_labels, module, object_set_empty, objects_empty, workspace_empty):
    labels = numpy.zeros_like(volume_labels)

    labels[4, 5, 5] = 1
    labels[2, 4, 15] = 1
    labels[6, 15, 4] = 1
    labels[5, 17, 17] = 1

    objects_empty.segmented = volume_labels

    module.x_name.value = "InputObjects"
    module.y_name.value = "OutputObjects"
    module.structuring_element.value = "ball,2"

    module.run(workspace_empty)

    actual = object_set_empty.get_objects("OutputObjects").segmented

    labels = skimage.morphology.binary_dilation(labels, skimage.morphology.ball(2))

    expected = labels

    numpy.testing.assert_array_equal(actual, expected)


def test_2d_multiple_seeds_per_obj(image_labels, module, object_set_empty, objects_empty, workspace_empty):
    # Make an object with more than one internal maximum
    image_labels[2:9, 2:11] = 1
    image_labels[2:5, 6] = 0
    image_labels[7:9, 6] = 0

    labels = numpy.zeros_like(image_labels)
    # This object should now have two seeds
    labels[5, 4] = 1
    labels[5, 8] = 1
    labels[4, 15] = 1
    labels[15, 4] = 1
    labels[17, 17] = 1

    objects_empty.segmented = image_labels

    module.x_name.value = "InputObjects"
    module.y_name.value = "OutputObjects"
    module.structuring_element.value = "disk,2"

    module.run(workspace_empty)

    actual = object_set_empty.get_objects("OutputObjects").segmented

    labels = skimage.morphology.binary_dilation(labels, skimage.morphology.disk(2))

    expected = labels

    numpy.testing.assert_array_equal(actual, expected)


def test_2d_max_seeds_per_object(image_labels, module, object_set_empty, objects_empty, workspace_empty):
    # Make an object with more than one internal maximum
    image_labels[2:9, 2:11] = 1
    image_labels[2:5, 6] = 0
    image_labels[7:9, 6] = 0

    labels = numpy.zeros_like(image_labels)
    # This object should normally get two seeds, but we're going to
    # enforce a maximum of 1
    labels[5, 4] = 1
    labels[5, 8] = 1
    labels[4, 15] = 1
    labels[15, 4] = 1
    labels[17, 17] = 1

    objects_empty.segmented = image_labels

    module.x_name.value = "InputObjects"
    module.y_name.value = "OutputObjects"
    module.structuring_element.value = "disk,0"
    module.max_seeds_per_obj.value = 1

    module.run(workspace_empty)

    actual = object_set_empty.get_objects("OutputObjects").segmented

    labels = skimage.morphology.binary_dilation(labels, skimage.morphology.disk(0))

    expected = labels

    unequal_pos = tuple(int(x) for x in numpy.where(actual != expected))

    assert unequal_pos == (5, 8) or unequal_pos == (5, 4)
