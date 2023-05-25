# coding=utf-8

"""
Author: Tim Becker, Juan Caicedo, Claire McQuin, with 
some modifications by Volker Hilsenstein incorporating code snippets from Eric Czech

The BSD 3-Clause License

Copyright © 2003 - 2018 Broad Institute, Inc. All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

    1.  Redistributions of source code must retain the above copyright notice,
        this list of conditions and the following disclaimer.

    2.  Redistributions in binary form must reproduce the above copyright
        notice, this list of conditions and the following disclaimer in the
        documentation and/or other materials provided with the distribution.

    3.  Neither the name of the Broad Institute, Inc. nor the names of its
        contributors may be used to endorse or promote products derived from
        this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED “AS IS.”  BROAD MAKES NO EXPRESS OR IMPLIED
REPRESENTATIONS OR WARRANTIES OF ANY KIND REGARDING THE SOFTWARE AND
COPYRIGHT, INCLUDING, BUT NOT LIMITED TO, WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE, CONFORMITY WITH ANY DOCUMENTATION,
NON-INFRINGEMENT, OR THE ABSENCE OF LATENT OR OTHER DEFECTS, WHETHER OR NOT
DISCOVERABLE. IN NO EVENT SHALL BROAD, THE COPYRIGHT HOLDERS, OR CONTRIBUTORS
BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO PROCUREMENT OF SUBSTITUTE
GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT
OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF, HAVE REASON TO KNOW, OR IN
FACT SHALL KNOW OF THE POSSIBILITY OF SUCH DAMAGE.

If, by operation of law or otherwise, any of the aforementioned warranty
disclaimers are determined inapplicable, your sole remedy, regardless of the
form of action, including, but not limited to, negligence and strict
liability, shall be replacement of the software with an updated version if one
exists.

Development of CellProfiler has been funded in whole or in part with federal
funds from the National Institutes of Health, the National Science Foundation,
and the Human Frontier Science Program.
"""

import logging
import numpy
import pkg_resources
import requests
import sys
import time
import numpy as np
import os.path
import cellprofiler.module
import cellprofiler.setting
from skimage import transform 

if sys.platform.startswith('win'):
    os.environ["KERAS_BACKEND"] = "cntk"
else:
    os.environ["KERAS_BACKEND"] = "tensorflow"

import keras 

logger = logging.getLogger(__name__)

option_dict_conv = {"activation": "relu", "padding": "same"}
option_dict_bn = { "momentum": 0.9}


__doc__ = """\
ClassifyPixels-Unet calculates pixel wise classification using an UNet 
network. The default network model is trained to identify nuclei, background 
and the nuclei boundary. Classification results are returned as three channel 
images: 

* red channel stores background classification
* green channel stores nuclei classification
* blue channel stores boundary classification

In the simplest use case, the classifications are converted to gray value images 
using the module ColorToGray. The module IdentifyPrimaryObjects can be 
used to identify example images in the nuclei channel (green channel). 

The default UNet model is downloaded and stored on the local machine. To 
replace the model the function  download_file_from_google_drive needs to 
be updated.  


Author: Tim Becker, Juan Caicedo, Claire McQuinn
some modifications by Volker Hilsenstein incorporating code snippets from Eric Czech
"""


class ClassifyPixelsUnet(cellprofiler.module.ImageProcessing):
    module_name = "ClassifyPixels-Unet"
    variable_revision_number = 1

    def run(self, workspace):
        input_image = workspace.image_set.get_image(self.x_name.value)

        input_shape = input_image.pixel_data.shape

        t0 = time.time()
        model = unet_initialize(input_shape)
        t1 = time.time()
        logger.debug('UNet initialization took {} seconds '.format(t1 - t0))

        self.function = lambda input_image: unet_classify(model, input_image)

        super(ClassifyPixelsUnet, self).run(workspace)


def unet_initialize(input_shape, automated_shape_adjustment=True):
    """initialize a unet of size shape, with optiaonel size adjustment if necessary

    Args: 
        input_shape: tuple 
        automated_shapte_adjustemt: boolean flag, if True shape will be adjusted to a compatible shape
    """ 
    unet_shape = unet_shape_resize(input_shape, 3)
    if input_shape != unet_shape and not automated_shape_adjustment:
        raise ValueError(
            "Input shape not compatible with 3 max-pool layers. Consider setting automated_shape_adjustment=True.")
    
    # create model
    dim1, dim2 = unet_shape

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
        model_id = "1I9j4oABbcV8EnvO_ufACXP9e4KyfHMtE"

        download_file_from_google_drive(model_id, weights_filename)

    model.load_weights(weights_filename)

    return model

def unet_shape_resize(shape, n_pooling_layers):
    """Resize shape for compatibility with UNet architecture
    
    Args:
        shape: Shape of images to be resized in format HW[D1, D2, ...] where any 
            trailing dimensions after the first two are ignored
        n_pooling_layers: Number of pooling (or upsampling) layers in network
    Returns:
        Shape with HW sizes transformed to nearest value acceptable by network

    suggested by Eric Czech
    """
    base = 2**n_pooling_layers
    rcsh = np.round(np.array(shape[:2]) / base).astype(int)
    # Combine HW axes transformation with trailing shape dimensions 
    # (being careful not to return 0-length axes)
    return tuple(base * np.clip(rcsh, 1, None)) + tuple(shape[2:])
    
def unet_image_resize(image, n_pooling_layers):
    """Resize image for compatibility with UNet architecture

    Args:
        image: Image to be resized in format HW[D1, D2, ...] where any 
            trailing dimensions after the first two are ignored
        n_pooling_layers: Number of pooling (or upsampling) layers in network
    Returns:
        Image with HW dimensions resized to nearest value acceptable by network
    
    Reference + Author:
        Eric Czech
        https://github.com/CellProfiler/CellProfiler-plugins/issues/65
    """
    shape = unet_shape_resize(image.shape, n_pooling_layers)
    # Note here that the type and range of the image will either not change
    # or become float64, 0-1 (which makes no difference w/ subsequent min/max scaling)
    return image if shape == image.shape else transform.resize(
        image, shape, mode='reflect', anti_aliasing=True)


def unet_classify(model, input_image, resize_to_model=True):
    dim1, dim2 = input_image.shape
    mdim1, mdim2 = model.input_shape[1:3]
    needs_resize = False if (dim1, dim2) == (mdim1, mdim2) else True
    if needs_resize:
        if resize_to_model:
            input_image = transform.resize(input_image, (mdim1, mdim2), anti_aliasing=True)
        else:
            raise ValueError("image size does not match model size, set resize_to_model=True")
    images = input_image.reshape((-1, mdim1, mdim2, 1))
    
    # scale min, max to [0.0,1.0]
    images = images.astype(numpy.float32)
    images = images - numpy.min(images)
    images = images.astype(numpy.float32) / numpy.max(images)
    
    start = time.time()
    pixel_classification = model.predict(images, batch_size=1)
    end = time.time()
    logger.debug('UNet segmentation took {} seconds '.format(end - start))

    retval = pixel_classification[0, :, :, :]
    if needs_resize:
        retval = transform.resize(retval, (dim1, dim2, retval.shape[2]))
    return retval

def get_core(dim1, dim2):
    x = keras.layers.Input(shape=(dim1, dim2, 1))
    
    a = keras.layers.Conv2D(64, (3, 3) , **option_dict_conv)(x)
    a = keras.layers.BatchNormalization(**option_dict_bn)(a)

    a = keras.layers.Conv2D(64, (3, 3), **option_dict_conv)(a)
    a = keras.layers.BatchNormalization(**option_dict_bn)(a)

    y = keras.layers.MaxPooling2D()(a)

    b = keras.layers.Conv2D(128, (3, 3), **option_dict_conv)(y)
    b = keras.layers.BatchNormalization(**option_dict_bn)(b)

    b = keras.layers.Conv2D(128, (3, 3), **option_dict_conv)(b)
    b = keras.layers.BatchNormalization(**option_dict_bn)(b)

    y = keras.layers.MaxPooling2D()(b)

    c = keras.layers.Conv2D(256, (3, 3), **option_dict_conv)(y)
    c = keras.layers.BatchNormalization(**option_dict_bn)(c)

    c = keras.layers.Conv2D(256, (3, 3), **option_dict_conv)(c)
    c = keras.layers.BatchNormalization(**option_dict_bn)(c)

    y = keras.layers.MaxPooling2D()(c)

    d = keras.layers.Conv2D(512, (3, 3), **option_dict_conv)(y)
    d = keras.layers.BatchNormalization(**option_dict_bn)(d)

    d = keras.layers.Conv2D(512, (3, 3), **option_dict_conv)(d)
    d = keras.layers.BatchNormalization(**option_dict_bn)(d)

    # UP

    d = keras.layers.UpSampling2D()(d)
    y = keras.layers.merge.concatenate([d, c], axis=3)

    e = keras.layers.Conv2D(256, (3, 3), **option_dict_conv)(y)
    e = keras.layers.BatchNormalization(**option_dict_bn)(e)

    e = keras.layers.Conv2D(256, (3, 3), **option_dict_conv)(e)
    e = keras.layers.BatchNormalization(**option_dict_bn)(e)

    e = keras.layers.UpSampling2D()(e)

    y = keras.layers.merge.concatenate([e, b], axis=3)

    f = keras.layers.Conv2D(128, (3, 3), **option_dict_conv)(y)
    f = keras.layers.BatchNormalization(**option_dict_bn)(f)

    f = keras.layers.Conv2D(128, (3, 3), **option_dict_conv)(f)
    f = keras.layers.BatchNormalization(**option_dict_bn)(f)

    f = keras.layers.UpSampling2D()(f)
    
    y = keras.layers.merge.concatenate([f, a], axis=3)

    y = keras.layers.Conv2D(64, (3, 3), **option_dict_conv)(y)
    y = keras.layers.BatchNormalization(**option_dict_bn)(y)

    y = keras.layers.Conv2D(64, (3, 3), **option_dict_conv)(y)
    y = keras.layers.BatchNormalization(**option_dict_bn)(y)

    return [x, y]

def get_model_3_class(dim1, dim2, activation="softmax"):
    [x, y] = get_core(dim1, dim2)

    y = keras.layers.Conv2D(3, (1, 1), **option_dict_conv)(y)

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
