import numpy
import numpy.random
import numpy.testing
import pytest
import cellprofiler.object

import constrainobjects


instance = constrainobjects.ConstrainObjects


@pytest.fixture(scope="function")
def reference_empty():
    obj = cellprofiler.object.Objects()

    return obj


@pytest.fixture(scope="function")
def object_set_empty(objects_empty, reference_empty):
    objects_set = cellprofiler.object.ObjectSet()
    objects_set.add_objects(objects_empty, "InputObjects")
    objects_set.add_objects(reference_empty, "ReferenceObjects")

    return objects_set


@pytest.fixture(scope="function")
def image_labels():
    labels = numpy.zeros((20, 20), dtype=numpy.uint16)

    # Make some child objects
    labels[2:7, 2:7] = 1
    labels[2:7, 14:19] = 2
    labels[14:19, 2:7] = 3
    labels[14:20, 14:20] = 4
    # One protruding object
    labels[9:13, 9:13] = 5

    return labels


@pytest.fixture(scope="function")
def image_reference():
    labels = numpy.zeros((20, 20), dtype=numpy.uint16)

    # Make some parent objects
    labels[1:8, 1:8] = 1
    labels[1:8, 13:20] = 2
    labels[13:20, 1:8] = 3
    labels[10:18, 10:18] = 4

    return labels


def test_2d_ignore(image_labels, image_reference, module, object_set_empty, objects_empty,
                   reference_empty, workspace_empty):
    labels = image_labels.copy()
    reference = image_reference.copy()

    objects_empty.segmented = labels
    reference_empty.segmented = reference

    module.x_name.value = "InputObjects"
    module.y_name.value = "OutputObjects"
    module.reference_name.value = "ReferenceObjects"

    module.run(workspace_empty)

    actual = object_set_empty.get_objects("OutputObjects").segmented

    expected = labels.copy()
    # The piece of object 4 outside of the parent should be removed
    # and object 5 should be ignored
    expected[14:20, 18:20] = 0
    expected[18:20, 14:20] = 0

    numpy.testing.assert_array_equal(actual, expected)


def test_2d_remove_protrude(image_labels, image_reference, module, object_set_empty, objects_empty,
                            reference_empty, workspace_empty):
    labels = image_labels.copy()
    reference = image_reference.copy()

    objects_empty.segmented = labels
    reference_empty.segmented = reference

    module.x_name.value = "InputObjects"
    module.y_name.value = "OutputObjects"
    module.reference_name.value = "ReferenceObjects"

    module.coersion_method.value = constrainobjects.METHOD_REMOVE

    module.run(workspace_empty)

    actual = object_set_empty.get_objects("OutputObjects").segmented

    expected = labels.copy()
    # The piece of object 4 outside of the parent should be removed
    # and the part of object 5 inside object 4 should be removed
    expected[14:20, 18:20] = 0
    expected[18:20, 14:20] = 0
    expected[10:13, 10:13] = 0

    numpy.testing.assert_array_equal(actual, expected)


def test_2d_remove_orphans(image_labels, image_reference, module, object_set_empty, objects_empty,
                            reference_empty, workspace_empty):
    labels = image_labels.copy()
    reference = image_reference.copy()

    objects_empty.segmented = labels
    reference_empty.segmented = reference

    module.x_name.value = "InputObjects"
    module.y_name.value = "OutputObjects"
    module.reference_name.value = "ReferenceObjects"

    module.remove_orphans.value = True

    module.run(workspace_empty)

    actual = object_set_empty.get_objects("OutputObjects").segmented

    expected = labels.copy()
    # The piece of object 4 outside of the parent should be removed
    expected[14:20, 18:20] = 0
    expected[18:20, 14:20] = 0
    # Object 5 should be removed altogether
    expected[expected == 5] = 0

    numpy.testing.assert_array_equal(actual, expected)


@pytest.fixture(scope="function")
def volume_labels():
    labels = numpy.zeros((10, 20, 20), dtype=numpy.uint16)

    # Make some child objects
    labels[2:7, 2:7, 2:7] = 1
    labels[2:5, 2:7, 14:19] = 2
    labels[5:9, 14:19, 2:7] = 3
    labels[3:8, 14:20, 14:20] = 4
    # One protruding object
    labels[0:9, 9:13, 9:13] = 5

    return labels


@pytest.fixture(scope="function")
def volume_reference():
    labels = numpy.zeros((10, 20, 20), dtype=numpy.uint16)

    # Make some parent objects
    labels[2:7, 1:8, 1:8] = 1
    labels[2:5, 1:8, 13:20] = 2
    labels[5:9, 13:20, 1:8] = 3
    labels[3:8, 10:18, 10:18] = 4

    return labels


def test_3d_ignore(volume_labels, volume_reference, module, object_set_empty, objects_empty,
                   reference_empty, workspace_empty):
    labels = volume_labels.copy()
    reference = volume_reference.copy()

    objects_empty.segmented = labels
    reference_empty.segmented = reference

    module.x_name.value = "InputObjects"
    module.y_name.value = "OutputObjects"
    module.reference_name.value = "ReferenceObjects"

    module.run(workspace_empty)

    actual = object_set_empty.get_objects("OutputObjects").segmented

    expected = labels.copy()
    # The piece of object 4 outside of the parent should be removed
    # and object 5 should be ignored
    expected[3:8, 14:20, 18:20] = 0
    expected[3:8, 18:20, 14:20] = 0

    numpy.testing.assert_array_equal(actual, expected)


def test_3d_remove_protrude(volume_labels, volume_reference, module, object_set_empty, objects_empty,
                            reference_empty, workspace_empty):
    labels = volume_labels.copy()
    reference = volume_reference.copy()

    objects_empty.segmented = labels
    reference_empty.segmented = reference

    module.x_name.value = "InputObjects"
    module.y_name.value = "OutputObjects"
    module.reference_name.value = "ReferenceObjects"

    module.coersion_method.value = constrainobjects.METHOD_REMOVE

    module.run(workspace_empty)

    actual = object_set_empty.get_objects("OutputObjects").segmented

    expected = labels.copy()
    # The piece of object 4 outside of the parent should be removed
    # and the part of object 5 inside object 4 should be removed
    expected[3:8, 14:20, 18:20] = 0
    expected[3:8, 18:20, 14:20] = 0
    expected[3:8, 10:13, 10:13] = 0

    numpy.testing.assert_array_equal(actual, expected)


def test_3d_remove_orphans(volume_labels, volume_reference, module, object_set_empty, objects_empty,
                           reference_empty, workspace_empty):
    labels = volume_labels.copy()
    reference = volume_reference.copy()

    objects_empty.segmented = labels
    reference_empty.segmented = reference

    module.x_name.value = "InputObjects"
    module.y_name.value = "OutputObjects"
    module.reference_name.value = "ReferenceObjects"

    module.remove_orphans.value = True

    module.run(workspace_empty)

    actual = object_set_empty.get_objects("OutputObjects").segmented

    expected = labels.copy()
    # The piece of object 4 outside of the parent should be removed
    expected[3:8, 14:20, 18:20] = 0
    expected[3:8, 18:20, 14:20] = 0
    # Object 5 should be removed altogether
    expected[expected == 5] = 0

    numpy.testing.assert_array_equal(actual, expected)
