import pytest

from unittest.mock import patch

from cellprofiler.modules import noise2void
from n2v.models import N2V

instance = noise2void.Noise2Void

AXES_3D = 'ZYX'
AXES_COLOR_3D = 'ZYXC'
AXES_COLOR_2D = 'YXC'
AXES_2D = 'YX'
DEFAULT_TILES_3D = (2, 4, 4)
DEFAULT_TILES_2D = (2, 1)


@pytest.fixture(scope="function")
def module(request):
    instance = getattr(request.module, "instance")

    return instance()


def test_3d_support(module):
    assert module.volumetric()


def test_number_of_visible_settings_color(module):
    module.color.value = True

    visible_settings = module.visible_settings()
    assert len(visible_settings) == 4
    assert all(setting in visible_settings for setting in [
               module.ml_model, module.color])
    assert module.manual_slicing not in visible_settings


def test_no_slicing_settings_when_color_toggled_true(module):
    module.manual_slicing.value = True
    module.color.value = True

    visible_settings = module.visible_settings()
    assert len(visible_settings) == 4
    assert all(setting in visible_settings for setting in [
               module.ml_model, module.color])
    assert module.manual_slicing not in visible_settings


def test_number_of_default_visibile_settings(module):

    # given
    settings_no_manual_tiles = module.visible_settings()  # default settings

    # then
    assert len(settings_no_manual_tiles) == 5
    assert all(setting in settings_no_manual_tiles for setting in [
               module.ml_model, module.color, module.manual_slicing])


def test_number_of_settings_manual_tile_choice(module):

    # when
    module.manual_slicing.value = True  # activate manual tile selection

    visible_settings = module.visible_settings()

    # then
    assert len(visible_settings) == 6
    assert all(setting in visible_settings for setting in [
               module.ml_model, module.color, module.manual_slicing,
               module.slicing_configuration])


@patch('cellprofiler.modules.noise2void.N2V', autospec=True)
def test_n2v_creation(N2V, module, workspace):

    module.x_name.value = 'example'
    module.ml_model.value = 'Default Input Folder sub-folder|Documents/CellProfiler/data/n2v_3D'
    module.run(workspace)

    # TODO check if this is multiplatform compatible
    N2V.assert_called_with(
        None, 'n2v_3D', '/home/nesta/Documents/CellProfiler/data')


@patch.object(N2V, 'predict')  # default == no color, no manual slicing
def test_run_default(pred, module, workspace):

    image_name = 'example'
    image = workspace.image_set.get_image(image_name)
    image_array = image.image
    module.x_name.value = image_name
    module.ml_model.value = 'Default Input Folder sub-folder|Documents/CellProfiler/data/n2v_3D'
    module.run(workspace)

    if not image.volumetric:
        pred.assert_called_with(image_array, axes=AXES_2D)
    else:
        pred.assert_called_with(
            image_array, axes=AXES_3D)


# make sure color axis is added to axes configuration. tiles not available when color == True
@patch.object(N2V, 'predict')
def test_run_color(pred, module, workspace):

    image_name = 'example'
    image = workspace.image_set.get_image(image_name)
    image_array = image.image
    module.x_name.value = image_name
    module.ml_model.value = 'Default Input Folder sub-folder|Documents/CellProfiler/data/n2v_3D'
    module.color.value = True
    module.run(workspace)

    if not image.volumetric:
        pred.assert_called_with(image_array, axes=AXES_COLOR_2D)
    else:
        pred.assert_called_with(
            image_array, axes=AXES_COLOR_3D)


# make sure custom tiles end up in actual n2v call
@patch.object(N2V, 'predict')
def test_run_manual_tiles(pred, module, workspace):

    image_name = 'example'
    image = workspace.image_set.get_image(image_name)
    image_array = image.image
    module.x_name.value = image_name
    module.ml_model.value = 'Default Input Folder sub-folder|Documents/CellProfiler/data/n2v_3D'
    module.manual_slicing.value = True
    module.slicing_configuration.value = '(1,2,3)' if image.volumetric else '(1,2)'

    module.run(workspace)

    if not image.volumetric:
        pred.assert_called_with(
            image_array, axes=AXES_2D, n_tiles=(1, 2))
    else:
        pred.assert_called_with(
            image_array, axes=AXES_3D, n_tiles=(1, 2, 3))


@patch.object(N2V, 'predict')
def test_wrong_tile_dimensionality_leads_to_run_with_no_tiles(pred, module, workspace):
    image_name = 'example'
    image = workspace.image_set.get_image(image_name)
    image_array = image.image
    module.x_name.value = image_name
    module.ml_model.value = 'Default Input Folder sub-folder|Documents/CellProfiler/data/n2v_3D'

    module.slicing_configuration.value = '(1,2)' if image.volumetric else '(1,2,3)'
    module.run(workspace)

    if not image.volumetric:
        pred.assert_called_with(image_array, axes=AXES_2D)
    else:
        pred.assert_called_with(image_array, axes=AXES_3D)


def test_2d_tile_parsing(module):
    values_to_test = ["(1,2)", " (1,2)", " (1,2) ", " (1 , 2)",
                      " (  1 ,2)", "1,2", "1,2)", "( 1,2"]
    assert all(parsed == (1, 2) for parsed in list(
        map(module.convert_string_to_tuple, values_to_test)))


def test_3d_tile_parsing(module):
    values_to_test = ["(1,2,2)", " (1,2,2)", " (1,2,2) ",
                      " (1 , 2,2)", " (  1 ,2 , 2)", "1,2,2", "1,2,2)", "( 1,2,2"]
    assert all(parsed == (1, 2, 2) for parsed in list(
        map(module.convert_string_to_tuple, values_to_test)))

