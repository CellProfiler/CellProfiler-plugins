import numpy
import numpy.testing
import skimage.morphology
import skimage.segmentation
import centrosome.cpmorphology
import pytest

import mergeobjects


instance = mergeobjects.MergeObjects


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


def make_params():
    # Format:
    # [use, method, vals[]]
    params = []
    methods = [mergeobjects.A_ABSOLUTE, mergeobjects.A_RELATIVE]
    abs_vals = [0, 10, 20, 50]
    rel_vals = [0.001, 0.01, 0.1, 1.0]
    # Add non used
    params.append([False, None, []])
    for method in methods:
        if method == mergeobjects.A_ABSOLUTE:
            params += [[True, method, val] for val in abs_vals]
        else:
            params += [[True, method, val] for val in rel_vals]
    return params


@pytest.fixture(
    scope="module",
    params=make_params()
)
def contact_area_params(request):
    return request.param


def test_run(object_set_with_data, module, workspace_with_data, remove_below, contact_area_params):

    use_contact_area, contact_method, relabs_neighbor_size = contact_area_params

    module.x_name.value = "InputObjects"
    module.y_name.value = "OutputObjects"
    module.size.value = 6.
    module.remove_below_threshold.value = remove_below
    module.use_contact_area.value = use_contact_area
    if use_contact_area:
        module.contact_area_method.value = contact_method
        if contact_method == mergeobjects.A_ABSOLUTE:
            module.abs_neighbor_size.value = relabs_neighbor_size
        else:
            module.rel_neighbor_size.value = relabs_neighbor_size

    module.run(workspace_with_data)

    actual = workspace_with_data.object_set.get_objects("OutputObjects").segmented

    if actual.ndim == 2:
        factor = 3 ** 2
    else:
        factor = (4.0 / 3.0) * (3 ** 3)

    size = numpy.pi * factor

    expected = object_set_with_data.get_objects("InputObjects").segmented

    merged = numpy.copy(expected)
    sizes = numpy.bincount(expected.ravel())
    mask_sizes = (sizes < size) & (sizes != 0)

    if use_contact_area and contact_method == mergeobjects.A_RELATIVE:
        border_mask = skimage.segmentation.find_boundaries(expected, mode='inner')
        surface_areas = numpy.bincount(expected[border_mask].ravel())

    for n in numpy.nonzero(mask_sizes)[0]:
        mask = expected == n
        bound = skimage.segmentation.find_boundaries(mask, mode='outer')
        neighbors = numpy.bincount(expected[bound].ravel())
        if len(neighbors) == 1:
            if remove_below:
                max_neighbor = 0
            else:
                continue
        else:
            neighbors[0] = 0
            max_neighbor = numpy.argmax(neighbors)

        if not use_contact_area:
            merged[merged == n] = max_neighbor
        else:
            if contact_method == mergeobjects.A_ABSOLUTE:
                neighbor_size = relabs_neighbor_size
                conditional = neighbors[max_neighbor] > relabs_neighbor_size
            else:
                neighbor_size = relabs_neighbor_size
                if remove_below and max_neighbor == 0:
                    conditional = True
                else:
                    conditional = (float(neighbors[max_neighbor]) / surface_areas[n]) > relabs_neighbor_size
            if neighbor_size == 0 or conditional:
                merged[merged == n] = max_neighbor

    expected = centrosome.cpmorphology.relabel(merged)[0]

    numpy.testing.assert_array_equal(actual, expected)


def test_2d_regular(image_labels, module, object_set_empty, objects_empty, workspace_empty):
    labels = image_labels.copy()
    labels[5, 5] = 5
    labels[2, 15] = 6
    labels[15, 2] = 7
    labels[15, 15] = 8

    objects_empty.segmented = labels

    module.x_name.value = "InputObjects"
    module.y_name.value = "OutputObjects"
    module.size.value = 2.

    module.run(workspace_empty)

    actual = object_set_empty.get_objects("OutputObjects").segmented
    expected = image_labels

    numpy.testing.assert_array_equal(actual, expected)


def test_3d_regular(volume_labels, module, object_set_empty, objects_empty, workspace_empty):
    labels = volume_labels.copy()
    labels[5, 5, 5] = 5
    labels[2, 2, 15] = 6
    labels[5, 15, 2] = 7
    labels[5, 15, 15] = 8

    objects_empty.segmented = labels

    module.x_name.value = "InputObjects"
    module.y_name.value = "OutputObjects"
    module.size.value = 2.

    module.run(workspace_empty)

    actual = object_set_empty.get_objects("OutputObjects").segmented
    expected = volume_labels

    numpy.testing.assert_array_equal(actual, expected)


def test_unchanged_3d_merge_large_object(volume_labels, module, object_set_empty, objects_empty, workspace_empty):
    labels = volume_labels.copy()
    # Create a 'large' object
    labels[5:10, 4:6, 4:6] = 5

    objects_empty.segmented = labels

    module.x_name.value = "InputObjects"
    module.y_name.value = "OutputObjects"
    # Set size below minimum
    module.size.value = 3.

    module.run(workspace_empty)

    actual = object_set_empty.get_objects("OutputObjects").segmented
    expected = labels

    # Since the 3D size is above the minimum size threshold, no object should be merged
    numpy.testing.assert_array_equal(actual, expected)


def test_changed_3d_merge_large_object(volume_labels, module, object_set_empty, objects_empty, workspace_empty):
    labels = volume_labels.copy()
    # Create a 'large' object
    labels[5:10, 4:6, 4:6] = 5

    objects_empty.segmented = labels

    module.x_name.value = "InputObjects"
    module.y_name.value = "OutputObjects"
    # Set size below minimum
    module.size.value = 3.
    # Set to planewise so the 'large' object is merged at each plane
    module.plane_wise.value = True

    module.run(workspace_empty)

    actual = object_set_empty.get_objects("OutputObjects").segmented
    expected = volume_labels

    # We're filling plane-wise here, so each 2D plane should have the object merged
    numpy.testing.assert_array_equal(actual, expected)


def test_2d_keep_nonneighbored_objects(image_labels, module, object_set_empty, objects_empty, workspace_empty):
    labels = image_labels.copy()
    # Create "small" object
    labels[8:12, 9:11] = 5

    objects_empty.segmented = labels

    module.x_name.value = "InputObjects"
    module.y_name.value = "OutputObjects"
    module.size.value = 4.
    # Modify threshold removal procedure
    module.remove_below_threshold.value = False

    module.run(workspace_empty)

    actual = object_set_empty.get_objects("OutputObjects").segmented
    # Object with no neighbors should not be removed
    expected = labels

    numpy.testing.assert_array_equal(actual, expected)


def test_3d_keep_nonneighbored_object(volume_labels, module, object_set_empty, objects_empty, workspace_empty):
    labels = volume_labels.copy()
    labels[8:12, 9:11, 4:6] = 5

    objects_empty.segmented = labels

    module.x_name.value = "InputObjects"
    module.y_name.value = "OutputObjects"
    module.size.value = 4.
    # Modify threshold removal procedure
    module.remove_below_threshold.value = False

    module.run(workspace_empty)

    actual = object_set_empty.get_objects("OutputObjects").segmented
    # Object with no neighbors should not be removed
    expected = labels

    numpy.testing.assert_array_equal(actual, expected)


def test_2d_abs_neighbor_size_some(image_labels, module, object_set_empty, objects_empty, workspace_empty):
    labels = image_labels.copy()
    # Create an object which doesn't meet contact criteria
    labels[12:15, 0:1] = 7
    # Create one which does
    labels[2:8, 2:4] = 8
    # Create one which meets the criteria for one object but not another
    labels[10:12, 12:17] = 9
    labels[8:10, 14:16] = 9

    objects_empty.segmented = labels

    module.x_name.value = "InputObjects"
    module.y_name.value = "OutputObjects"
    module.size.value = 4.
    module.remove_below_threshold.value = False

    # Set the minimum contact area
    module.use_contact_area.value = True
    module.contact_area_method.value = mergeobjects.A_ABSOLUTE
    module.abs_neighbor_size.value = 5

    module.run(workspace_empty)

    actual = object_set_empty.get_objects("OutputObjects").segmented

    expected = labels.copy()
    # Objects with less than 6 contacting pixels stay
    expected[2:8, 2:4] = 1
    # Some objects are relabeled
    expected[expected == 7] = 5
    expected[expected == 9] = 6

    numpy.testing.assert_array_equal(actual, expected)


def test_2d_abs_neighbor_size_all(image_labels, module, object_set_empty, objects_empty, workspace_empty):
    labels = image_labels.copy()
    # Create an object which doesn't meet contact criteria
    labels[12:15, 0:1] = 7
    # Create one which does
    labels[2:8, 2:4] = 8
    # Create one which meets the criteria for one object but not another
    labels[10:12, 12:17] = 9
    labels[8:10, 14:16] = 9

    objects_empty.segmented = labels

    module.x_name.value = "InputObjects"
    module.y_name.value = "OutputObjects"
    module.size.value = 5.
    module.remove_below_threshold.value = False

    # Set the minimum contact area low so all objects get merged
    module.use_contact_area.value = True
    module.contact_area_method.value = mergeobjects.A_ABSOLUTE
    module.abs_neighbor_size.value = 3

    module.run(workspace_empty)

    actual = object_set_empty.get_objects("OutputObjects").segmented

    expected = image_labels.copy()
    # Have to set the weird one
    expected[10:12, 12:17] = 4
    expected[8:10, 14:16] = 4

    numpy.testing.assert_array_equal(actual, expected)


def test_2d_rel_neighbor_size_some(image_labels, module, object_set_empty, objects_empty, workspace_empty):
    labels = image_labels.copy()
    # Create an object which doesn't meet contact criteria
    labels[12:15, 0:1] = 7
    # Create one which does
    labels[2:8, 2:4] = 8
    # Create one which meets the criteria for one object but not another
    labels[10:12, 12:17] = 9
    labels[8:10, 14:16] = 9

    objects_empty.segmented = labels

    module.x_name.value = "InputObjects"
    module.y_name.value = "OutputObjects"
    module.size.value = 4.
    module.remove_below_threshold.value = False

    # Set the minimum contact area
    module.use_contact_area.value = True
    module.contact_area_method.value = mergeobjects.A_RELATIVE
    module.rel_neighbor_size.value = 0.5

    module.run(workspace_empty)

    actual = object_set_empty.get_objects("OutputObjects").segmented

    expected = labels.copy()
    # Objects with more than 50% contacting will be removed
    expected[12:15, 0:1] = 3
    # Some objects get relabeled
    expected[expected == 8] = 5
    expected[expected == 9] = 6

    numpy.testing.assert_array_equal(actual, expected)


def test_2d_rel_neighbor_size_all(image_labels, module, object_set_empty, objects_empty, workspace_empty):
    labels = image_labels.copy()
    # Create an object which doesn't meet contact criteria
    labels[12:15, 0:1] = 7
    # Create one which does
    labels[2:8, 2:4] = 8
    # Create one which meets the criteria for one object but not another
    labels[10:12, 12:17] = 9
    labels[8:10, 14:16] = 9

    objects_empty.segmented = labels

    module.x_name.value = "InputObjects"
    module.y_name.value = "OutputObjects"
    module.size.value = 5.
    module.remove_below_threshold.value = False

    # Set the minimum contact area low so all objects get merged
    module.use_contact_area.value = True
    module.contact_area_method.value = mergeobjects.A_ABSOLUTE
    module.rel_neighbor_size.value = 0.1

    module.run(workspace_empty)

    actual = object_set_empty.get_objects("OutputObjects").segmented

    expected = image_labels.copy()
    # Have to set the weird one
    expected[10:12, 12:17] = 4
    expected[8:10, 14:16] = 4

    numpy.testing.assert_array_equal(actual, expected)
