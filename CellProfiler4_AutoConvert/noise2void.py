#################################
#
# Imports from useful Python libraries
#
#################################

from os.path import split
from n2v.models import N2V


#################################
#
# Imports from CellProfiler
#
##################################
from cellprofiler_core.setting.choice import Choice
from cellprofiler_core.setting import Binary
from cellprofiler_core.setting.text import Directory
from cellprofiler_core.setting.text import Text
from cellprofiler_core.module import ImageProcessing
from cellprofiler_core.constants.module import IO_FOLDER_CHOICE_HELP_TEXT

__doc__ = """\
Noise2Void
=============

**Noise2Void** is a deep learning based image denoiser.

|

============ ============ ===============
Supports 2D? Supports 3D? Respects masks?
============ ============ ===============
    YES           YES           NO
============ ============ ===============

What do I need as input?
^^^^^^^^^^^^^^^^^^^^^^^^

**Noise2Void** expects a 2D or a 3D image. The 2D image may have color, the 3D image may only be grayscale.
This module only offers **Noise2Void**'s prediction (denoising) capabilities. Therefore, the module has to be configured to know path to a pre-trained machine learning model via its settings.
Information on training and example models can be gained from https://github.com/juglab/n2v.

What do I get as output?
^^^^^^^^^^^^^^^^^^^^^^^^
A denoised version of the input image. The dimensions and other properties of the image stay untouched.

Technical notes
^^^^^^^^^^^^^^^

Alongside n2v, Tensorflow 2 should be installed and configured correctly so that this module runs on GPU and not on CPU which is much slower.

References
^^^^^^^^^^

-  Krull, Alexander and Buchholz, Tim-Oliver and Jug, Florian (2019) “Noise2void-learning denoising from single noisy images” **Proceedings of the IEEE Conference on Computer Vision and Pattern Recognition 1**, 2129--2137. (`link <https://github.com/juglab/n2v>`__)

-  https://github.com/juglab/n2v

"""

#
# Constants
#
N2V_AXES_3D = 'ZYX'
N2V_AXES_2D = 'YX'
N2V_AXES_COLOR = 'C'


class Noise2Void(ImageProcessing):
    module_name = "Noise2Void"

    variable_revision_number = 1

    def create_settings(self):
        super(Noise2Void, self).create_settings()
        self.ml_model = Directory("Path to ML Model",
                                  doc="""\
Select the folder containing the machine learning model to be used.
This model has to be generated via the noise2void training. See
https://github.com/juglab/n2v/blob/master/examples/2D/denoising2D_RGB/01_training.ipynb
for an example of training.
"""
                                  )
        self.color = Binary("Process as color image?",
                            value=False,
                            doc="""\
Select whether your image should be processed as a color image or not.
""")
        self.manual_slicing = Binary("Slice Image manually?",
                                     value=False, doc="""\
If necessary, **Noise2Void** will slice your image into tiles automatically for a better memory fit. 
If you want to manually determine the size of the said tiles, check this setting.

Colored images **do not** support custom slicing as of right now!
""")
        self.slicing_configuration = Text("Tile size", value="(2,2,2)", doc="""\
You can provide an image slicing configuration for Noise2Void for a better memory fit. 
Specify your custom slicing configuration as follows:

- (x,y) for 2D Images
- (x,y,z) for 3D Images, whereas x,y and z are positive integers.

If your input cannot be parsed, no slicing configuration will be provided to n2v.
""")

        self.axes_configuration = Text(text="N2V Axes", value=N2V_AXES_3D, doc="""\
For internal use only.
Communicates axes configuration (2D or 3D, color or not) to n2v.
""")

        self.x_name.doc = """\
This is the image that the module operates on. You can choose any image
that is made available by a prior module.

**Noise2Void** will denoise this image using a tensorflow based neural network.
"""

    def settings(self):
        settings = super(Noise2Void, self).settings()
        return settings + [self.ml_model, self.slicing_configuration, self.color, self.axes_configuration]

    def visible_settings(self):
        visible_settings = super(Noise2Void, self).visible_settings()

        visible_settings += [self.ml_model, self.color]

        if not self.color:
            visible_settings += [self.manual_slicing]
            if self.manual_slicing:
                visible_settings += [self.slicing_configuration]
        return visible_settings

    #
    # This is the function that gets called during "run" to create the output image.
    #
    def denoise(self, pixels, ml_model,  final_tile_choice, color, axes):

        path = self.ml_model.get_absolute_path()
        (basedir, model_name) = split(path)

        try:
            model = N2V(config=None, name=model_name, basedir=basedir)
        except FileNotFoundError as e:
            raise FileNotFoundError(
                'Path ' + path + ' doesn\'t lead to valid model') from e
        if self.manual_slicing:
            tile_tuple = self.convert_string_to_tuple(final_tile_choice)
        if color or not self.manual_slicing or tile_tuple == None:
            axes = self.adjust_for_color(axes)
            pred = model.predict(pixels, axes=axes)
        else:
            pred = model.predict(pixels, axes=axes, n_tiles=tile_tuple)
        return pred

    def run(self, workspace):
        image = workspace.image_set.get_image(self.x_name.value)
        self.adjust_settings_for_dimensionality(image.volumetric)
        self.function = self.denoise

        super(Noise2Void, self).run(workspace)

    def volumetric(self):
        return True

    def adjust_settings_for_dimensionality(self, image_is_3d_in_workspace):
        if image_is_3d_in_workspace:
            self.axes_configuration.value = N2V_AXES_3D
        else:
            self.axes_configuration.value = N2V_AXES_2D

    def adjust_for_color(self, axes):
        axes.replace(N2V_AXES_COLOR, '')
        if self.color:
            axes += N2V_AXES_COLOR
        return axes

    def convert_string_to_tuple(self, text):
        try:
            text = text.strip()
            text = text.replace('(', '')
            text = text.replace(')', '')
            text = text.replace(' ', '')
            return tuple(map(int, text.split(',')))
        except ValueError:
            return None
