import logging
import os.path
import time

import cellprofiler.module
import cellprofiler.setting
import keras
import numpy
import pkg_resources
import requests
import tensorflow

logger = logging.getLogger(__name__)

option_dict_conv = {"activation": "relu", "border_mode": "same"}
option_dict_bn = {"mode": 0, "momentum": 0.9}


__doc__ = """\
tbd
"""


class UnetSegment(cellprofiler.module.ImageProcessing):
    module_name = "UnetSegment"
    variable_revision_number = 1

    def run(self, workspace):
        input_image = workspace.image_set.get_image(self.x_name.value)

        input_shape = input_image.pixel_data.shape

        t0 = time.time()
        model = unet_initialize(input_shape)
        t1 = time.time()
        logger.debug('UNet initialization took {} seconds '.format(t1 - t0))

        self.function = lambda input_image: unet_segmentation(model, input_image)

        super(UnetSegment, self).run(workspace)


def unet_initialize(input_shape):
    session = tensorflow.Session()
    # apply session
    keras.backend.set_session(session)
    # create model

    dim1, dim2 = input_shape

    # build model
    model = get_model_3_class(dim1, dim2)

    # load weights
    weights_filename = pkg_resources.resource_filename(
        "cellprofiler",
        os.path.join(".cache", "unet-checkpoint.hdf5")
    )

    if not os.path.exists(weights_filename):
        cache_directory = os.path.dirname(weights_filename)
        if not os.path.exists(cache_directory):
            os.makedirs(os.path.dirname(weights_filename))

        # Download the weights
        logger.debug("Downloading model weights to: {:s}".format(weights_filename))
        id = "146sae_bv2rJa4YoJr8Hlo-MFKfuepoMX"
        download_file_from_google_drive(id, weights_filename)

    model.load_weights(weights_filename)

    return model


def unet_segmentation(model, input_image):
    dim1, dim2 = input_image.shape

    images = input_image.reshape((-1, dim1, dim2, 1))

    images = images.astype(numpy.float32)
    images = images - numpy.min(images)
    images = images.astype(numpy.float32) / numpy.max(images)

    start = time.time()
    segmentation = model.predict(images, batch_size=1)
    end = time.time()
    logger.debug('UNet segmentation took {} seconds '.format(end - start))

    return segmentation[0, :, :, :]


def get_core(dim1, dim2):
    x = keras.layers.Input(shape=(dim1, dim2, 1))

    a = keras.layers.Convolution2D(64, 3, 3, **option_dict_conv)(x)
    a = keras.layers.BatchNormalization(**option_dict_bn)(a)

    a = keras.layers.Convolution2D(64, 3, 3, **option_dict_conv)(a)
    a = keras.layers.BatchNormalization(**option_dict_bn)(a)

    y = keras.layers.MaxPooling2D()(a)

    b = keras.layers.Convolution2D(128, 3, 3, **option_dict_conv)(y)
    b = keras.layers.BatchNormalization(**option_dict_bn)(b)

    b = keras.layers.Convolution2D(128, 3, 3, **option_dict_conv)(b)
    b = keras.layers.BatchNormalization(**option_dict_bn)(b)

    y = keras.layers.MaxPooling2D()(b)

    c = keras.layers.Convolution2D(256, 3, 3, **option_dict_conv)(y)
    c = keras.layers.BatchNormalization(**option_dict_bn)(c)

    c = keras.layers.Convolution2D(256, 3, 3, **option_dict_conv)(c)
    c = keras.layers.BatchNormalization(**option_dict_bn)(c)

    y = keras.layers.MaxPooling2D()(c)

    d = keras.layers.Convolution2D(512, 3, 3, **option_dict_conv)(y)
    d = keras.layers.BatchNormalization(**option_dict_bn)(d)

    d = keras.layers.Convolution2D(512, 3, 3, **option_dict_conv)(d)
    d = keras.layers.BatchNormalization(**option_dict_bn)(d)

    # UP

    d = keras.layers.UpSampling2D()(d)

    y = keras.layers.merge([d, c], concat_axis=3, mode="concat")

    e = keras.layers.Convolution2D(256, 3, 3, **option_dict_conv)(y)
    e = keras.layers.BatchNormalization(**option_dict_bn)(e)

    e = keras.layers.Convolution2D(256, 3, 3, **option_dict_conv)(e)
    e = keras.layers.BatchNormalization(**option_dict_bn)(e)

    e = keras.layers.UpSampling2D()(e)

    y = keras.layers.merge([e, b], concat_axis=3, mode="concat")

    f = keras.layers.Convolution2D(128, 3, 3, **option_dict_conv)(y)
    f = keras.layers.BatchNormalization(**option_dict_bn)(f)

    f = keras.layers.Convolution2D(128, 3, 3, **option_dict_conv)(f)
    f = keras.layers.BatchNormalization(**option_dict_bn)(f)

    f = keras.layers.UpSampling2D()(f)

    y = keras.layers.merge([f, a], concat_axis=3, mode="concat")

    y = keras.layers.Convolution2D(64, 3, 3, **option_dict_conv)(y)
    y = keras.layers.BatchNormalization(**option_dict_bn)(y)

    y = keras.layers.Convolution2D(64, 3, 3, **option_dict_conv)(y)
    y = keras.layers.BatchNormalization(**option_dict_bn)(y)

    return [x, y]


def get_model_3_class(dim1, dim2, activation="softmax"):
    [x, y] = get_core(dim1, dim2)

    y = keras.layers.Convolution2D(3, 1, 1, **option_dict_conv)(y)

    if activation is not None:
        y = keras.layers.Activation(activation)(y)

    model = keras.models.Model(x, y)

    return model


# https://stackoverflow.com/a/39225272
def download_file_from_google_drive(id, destination):
    url = "https://docs.google.com/uc?export=download"

    session = requests.Session()

    response = session.get(url, params={'id': id}, stream=True)
    token = get_confirm_token(response)

    if token:
        params = {
            'id': id,
            'confirm': token
        }
        response = session.get(url, params=params, stream=True)

    save_response_content(response, destination)


def get_confirm_token(response):
    for key, value in response.cookies.items():
        if key.startswith('download_warning'):
            return value

    return None


def save_response_content(response, destination):
    chunk_size = 32768

    with open(destination, "wb") as f:
        for chunk in response.iter_content(chunk_size):
            if chunk:  # filter out keep-alive new chunks
                f.write(chunk)
