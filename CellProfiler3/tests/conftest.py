# Something in CellProfiler is importing wx before we can set
# headless mode. Setting headless here efore importing anything
# else from CellProfiler.
import cellprofiler.preferences

cellprofiler.preferences.set_headless()

import cellprofiler.image
import cellprofiler.measurement
import cellprofiler.object
import cellprofiler.pipeline
import cellprofiler.workspace
import numpy
import skimage.data
import skimage.color
import skimage.filters
import skimage.measure
import pytest


@pytest.fixture(
    scope="module",
    params=[
        (skimage.data.camera()[0:128, 0:128], 2),
        (skimage.data.astronaut()[0:128, 0:128, :], 2),
        (numpy.tile(skimage.data.camera()[0:32, 0:32], (2, 1)).reshape(2, 32, 32), 3)
    ],
    ids=[
        "grayscale_image",
        "multichannel_image",
        "grayscale_volume"
    ]
)
def image(request):
    data, dimensions = request.param

    return cellprofiler.image.Image(image=data, dimensions=dimensions)


@pytest.fixture(scope="function")
def image_empty():
    image = cellprofiler.image.Image()

    return image


@pytest.fixture(scope="function")
def image_set(image, image_set_list):
    image_set = image_set_list.get_image_set(0)

    image_set.add("example", image)

    return image_set


@pytest.fixture(scope="function")
def image_set_empty(image_empty, image_set_list):
    image_set = image_set_list.get_image_set(0)
    image_set.add("example", image_empty)

    return image_set


@pytest.fixture(scope="function")
def image_set_list():
    return cellprofiler.image.ImageSetList()


@pytest.fixture(scope="function")
def measurements():
    return cellprofiler.measurement.Measurements()


@pytest.fixture(scope="function")
def module(request):
    instance = getattr(request.module, "instance")

    return instance()


@pytest.fixture(scope="function")
def objects(image):
    obj = cellprofiler.object.Objects()
    obj.parent_image = image

    return obj


@pytest.fixture(scope="function")
def objects_empty():
    obj = cellprofiler.object.Objects()

    return obj


@pytest.fixture(scope="function")
def object_set(objects):
    objects_set = cellprofiler.object.ObjectSet()
    objects_set.add_objects(objects, "InputObjects")

    return objects_set


@pytest.fixture(scope="function")
def object_set_empty(objects_empty):
    objects_set = cellprofiler.object.ObjectSet()
    objects_set.add_objects(objects_empty, "InputObjects")

    return objects_set


@pytest.fixture(scope="function")
def object_with_data(image):
    data = image.pixel_data

    if image.multichannel:
        data = skimage.color.rgb2gray(data)

    binary = data > skimage.filters.threshold_li(data)

    labels = skimage.measure.label(binary)

    objects = cellprofiler.object.Objects()

    objects.segmented = labels
    objects.parent_image = image

    return objects


@pytest.fixture(scope="function")
def object_set_with_data(object_with_data):
    objects_set = cellprofiler.object.ObjectSet()
    objects_set.add_objects(object_with_data, "InputObjects")

    return objects_set


@pytest.fixture(scope="function")
def pipeline():
    return cellprofiler.pipeline.Pipeline()


@pytest.fixture(scope="function")
def workspace(pipeline, module, image_set, object_set, measurements, image_set_list):
    return cellprofiler.workspace.Workspace(pipeline, module, image_set, object_set, measurements, image_set_list)


@pytest.fixture(scope="function")
def workspace_empty(pipeline, module, image_set_empty, object_set_empty, measurements, image_set_list):
    return cellprofiler.workspace.Workspace(pipeline, module, image_set_empty, object_set_empty, measurements, image_set_list)


@pytest.fixture(scope="function")
def workspace_with_data(pipeline, module, image_set, object_set_with_data, measurements, image_set_list):
    return cellprofiler.workspace.Workspace(pipeline, module, image_set, object_set_with_data,
                                            measurements, image_set_list)
