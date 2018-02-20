import cellprofiler.setting
import keras
import tensorflow
import numpy

option_dict_conv = {"activation": "relu", "border_mode": "same"}
option_dict_bn = {"mode": 0, "momentum": 0.9}


class UnetSegment(cellprofiler.module.ImageProcessing):
    category = "Image Segmentation"
    module_name = "UnetSegment"
    variable_revision_number = 1

    def is_aggregation_module(self):
        return True

    def create_settings(self):
        super(UnetSegment, self).create_settings()

    def settings(self):
        settings = super(UnetSegment, self).settings()
        return settings

    def run(self, workspace):
        self.function = unet_segmentation

        super(UnetSegment, self).run(workspace)

        images = workspace.image_set

        x_name = self.x_name.value
        x = images.get_image(x_name)
        x_data = x.pixel_data

        y_name = self.y_name.value
        y = images.get_image(y_name)
        y_data = y.pixel_data

        if self.show_window:
            workspace.display_data.x_data = x_data

            workspace.display_data.y_data = y_data

            workspace.display_data.dimensions = x.dimensions

    def post_group(self, workspace, grouping):
        pass

    def display_post_group(self, workspace, figure):
        pass


def unet_segmentation(input_image):
    session = tensorflow.Session()
    # apply session
    keras.backend.set_session(session)
    # create model

    print(input_image.shape)

    dim1 = input_image.shape[0]
    dim2 = input_image.shape[1]

    images = input_image.reshape((-1, dim1, dim2, 1))

    images = images.astype(numpy.float32)
    images = images - numpy.min(images)
    images = images.astype(numpy.float32) / numpy.max(images)

    # build model and load weights
    model = get_model_3_class(dim1, dim2)
    model.load_weights("/Users/tbecker/Documents/2017_08_unet/workspace/cp_plugin_test/unet_exp15_model.hdf5")

    unet_segmentation = model.predict(images, batch_size=1)

    return(unet_segmentation[0,:,:,:])


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
