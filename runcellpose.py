import numpy
import os
from cellpose import models
from skimage.transform import resize

from cellprofiler_core.image import Image
from cellprofiler_core.module.image_segmentation import ImageSegmentation
from cellprofiler_core.object import Objects
from cellprofiler_core.setting import Binary
from cellprofiler_core.setting.choice import Choice
from cellprofiler_core.setting.do_something import DoSomething
from cellprofiler_core.setting.subscriber import ImageSubscriber
from cellprofiler_core.setting.text import Integer, ImageName, Directory, Filename, Float

CUDA_LINK = "https://pytorch.org/get-started/locally/"

__doc__ = f"""\
RunCellpose
===========

**RunCellpose** uses a pre-trained machine learning model (Cellpose) to detect cells or nuclei in an image.
This module is useful for automating simple segmentation tasks in CellProfiler.
The module accepts greyscale input images and produces an object set. Probabilities can also be captured as an image.

Loading in a model will take slightly longer the first time you run it each session. When evaluating
performance you may want to consider the time taken to predict subsequent images.

Installation:
You'll want to run `pip install cellpose` (or if you want to upgrade to the most recent cellpose version:
`python -m pip install cellpose --upgrade`) on your CellProfiler Python environment to setup Cellpose. 
On the first time loading into CellProfiler, Cellpose will need to download some model files from the internet. This
may take some time. If you want to use a GPU to run the model, you'll need a compatible version of PyTorch and a
supported GPU. Instructions are avaiable at this link: {CUDA_LINK}

|

============ ============ ===============
Supports 2D? Supports 3D? Respects masks?
============ ============ ===============
YES          YES          NO
============ ============ ===============

"""

MODE_CELLS = "Cells"
MODE_NUCLEI = "Nuclei"
MODE_CUSTOM = "Custom"


class RunCellpose(ImageSegmentation):
    category = "Object Processing"

    module_name = "RunCellpose"

    variable_revision_number = 2

    def create_settings(self):
        super(RunCellpose, self).create_settings()

        self.expected_diameter = Integer(
            text="Expected object diameter",
            value=15,
            minval=0,
            doc="""\
The average diameter of the objects to be detected. Setting this to 0 will attempt to automatically detect object size.
Note that automatic diameter mode does not work when running on 3D images.

Cellpose models come with a pre-defined object diameter. Your image will be resized during detection to attempt to
match the diameter expected by the model. The default models have an expected diameter of ~16 pixels, if trying to
detect much smaller objects it may be more efficient to resize the image first using the Resize module.
""",
        )

        self.mode = Choice(
            text="Detection mode",
            choices=[MODE_NUCLEI, MODE_CELLS, MODE_CUSTOM],
            value=MODE_NUCLEI,
            doc="""\
CellPose comes with models for detecting nuclei or cells. Alternatively, you can supply a custom-trained model
generated using the command line or Cellpose GUI. Custom models can be useful if working with unusual cell types.
""",
        )

        self.use_gpu = Binary(
            text="Use GPU",
            value=False,
            doc=f"""\
If enabled, Cellpose will attempt to run detection on your system's graphics card (GPU).
Note that you will need a CUDA-compatible GPU and correctly configured PyTorch version, see this link for details:
{CUDA_LINK}

If disabled or incorrectly configured, Cellpose will run on your CPU instead. This is much slower but more compatible
with different hardware setups.

Note that, particularly when in 3D mode, lack of GPU memory can become a limitation. If a model crashes you may need to
re-start CellProfiler to release GPU memory. Resizing large images prior to running them through the model can free up
GPU memory.

"""
        )

        self.use_averaging = Binary(
            text="Use averaging",
            value=True,
            doc="""\
If enabled, CellPose will run it's 4 inbuilt models and take a consensus to determine the results. If disabled, only a
single model will be called to produce results. Disabling averaging is faster to run but less accurate."""
        )

        self.supply_nuclei = Binary(
            text="Supply nuclei image as well?",
            value=False,
            doc="""
When detecting whole cells, you can provide a second image featuring a nuclear stain to assist
the model with segmentation. This can help to split touching cells."""
        )

        self.nuclei_image = ImageSubscriber(
            "Select the nuclei image",
            doc="Select the image you want to use as the nuclear stain."
        )

        self.save_probabilities = Binary(
            text="Save probability image?",
            value=False,
            doc="""
If enabled, the probability scores from the model will be recorded as a new image.
Probability >0 is considered as being part of a cell.
You may want to use a higher threshold to manually generate objects.""",
        )

        self.probabilities_name = ImageName(
            "Name the probability image",
            "Probabilities",
            doc="Enter the name you want to call the probability image produced by this module.",
        )

        self.model_directory = Directory(
            "Location of the pre-trained model file",
            doc=f"""\
*(Used only when using a custom pre-trained model)*

Select the location of the pre-trained CellPose model file that will be used for detection."""
        )

        def get_directory_fn():
            """Get the directory for the rules file name"""
            return self.model_directory.get_absolute_path()

        def set_directory_fn(path):
            dir_choice, custom_path = self.model_directory.get_parts_from_path(path)

            self.model_directory.join_parts(dir_choice, custom_path)

        self.model_file_name = Filename(
            "Pre-trained model file name",
            "cyto_0",
            get_directory_fn=get_directory_fn,
            set_directory_fn=set_directory_fn,
            doc=f"""\
*(Used only when using a custom pre-trained model)*

This file can be generated by training a custom model withing the CellPose GUI or command line applications."""
        )

        self.gpu_test = DoSomething(
            "",
            "Test GPU",
            self.do_check_gpu,
            doc=f"""\
Press this button to check whether a GPU is correctly configured.

If you have a dedicated GPU, a failed test usually means that either your GPU does not support deep learning or the
required dependencies are not installed.

If you have multiple GPUs on your system, this button will only test the first one.
""",
        )

        self.flow_threshold = Float(
            text="Flow threshold",
            value=0.4,
            minval=0,
            doc="""Flow error threshold. All cells with errors below this threshold are kept. Recommended default is 0.4""",
        )

        self.dist_threshold = Float(
            text="Cell probability threshold",
            value=0.0,
            minval=-6.0,
            maxval=6.0,
            doc=f"""\
Cell probability threshold (all pixels with probability above threshold kept for masks). Recommended default is 0.0. """,
        )

    def settings(self):
        return [
            self.x_name,
            self.expected_diameter,
            self.mode,
            self.y_name,
            self.use_gpu,
            self.use_averaging,
            self.supply_nuclei,
            self.nuclei_image,
            self.save_probabilities,
            self.probabilities_name,
            self.model_directory,
            self.model_file_name,
            self.flow_threshold,
            self.dist_threshold
        ]

    def visible_settings(self):
        vis_settings = [self.mode, self.x_name]

        if self.mode.value != MODE_NUCLEI:
            vis_settings += [self.supply_nuclei]
            if self.supply_nuclei.value:
                vis_settings += [self.nuclei_image]
        if self.mode.value == MODE_CUSTOM:
            vis_settings += [self.model_directory, self.model_file_name]

        vis_settings += [self.expected_diameter, self.flow_threshold, self.dist_threshold, self.y_name, self.save_probabilities]

        if self.save_probabilities.value:
            vis_settings += [self.probabilities_name]

        vis_settings += [self.use_averaging, self.use_gpu]

        if self.use_gpu.value:
            vis_settings += [self.gpu_test]

        return vis_settings

    def run(self, workspace):
        if self.mode.value != MODE_CUSTOM:
            model = models.Cellpose(model_type='cyto' if self.mode.value == MODE_CELLS else 'nuclei',
                                    gpu=self.use_gpu.value)
        else:
            model_file = self.model_file_name.value
            model_directory = self.model_directory.get_absolute_path()
            model_path = os.path.join(model_directory, model_file)
            model = models.CellposeModel(pretrained_model=model_path, gpu=self.use_gpu.value)

        x_name = self.x_name.value
        y_name = self.y_name.value
        images = workspace.image_set
        x = images.get_image(x_name)
        dimensions = x.dimensions
        x_data = x.pixel_data

        if x.multichannel:
            raise ValueError("Color images are not currently supported. Please provide greyscale images.")

        if self.mode.value != "Nuclei" and self.supply_nuclei.value:
            nuc_image = images.get_image(self.nuclei_image.value)
            # CellPose expects RGB, we'll have a blank red channel, cells in green and nuclei in blue.
            if x.volumetric:
                x_data = numpy.stack((numpy.zeros_like(x_data), x_data, nuc_image.pixel_data), axis=1)
            else:
                x_data = numpy.stack((numpy.zeros_like(x_data), x_data, nuc_image.pixel_data), axis=-1)
            channels = [2, 3]
        else:
            channels = [0, 0]

        diam = self.expected_diameter.value if self.expected_diameter.value > 0 else None

        try:
            y_data, flows, *_ = model.eval(
                x_data,
                channels=channels,
                diameter=diam,
                net_avg=self.use_averaging.value,
                do_3D=x.volumetric,
                flow_threshold=self.flow_threshold.value,
                cellprob_threshold=self.dist_threshold.value

            )
        finally:
            if self.use_gpu.value and model.torch:
                # Try to clear some GPU memory for other worker processes.
                try:
                    from torch import cuda
                    cuda.empty_cache()
                except Exception as e:
                    print(f"Unable to clear GPU memory. You may need to restart CellProfiler to change models. {e}")

        y = Objects()
        y.segmented = y_data
        y.parent_image = x.parent_image
        objects = workspace.object_set
        objects.add_objects(y, y_name)

        if self.save_probabilities.value:
            # Flows come out sized relative to CellPose's inbuilt model size.
            # We need to slightly resize to match the original image.
            size_corrected = resize(flows[2], y_data.shape)
            prob_image = Image(
                size_corrected,
                parent_image=x.parent_image,
                convert=False,
                dimensions=len(size_corrected.shape),
            )

            workspace.image_set.add(self.probabilities_name.value, prob_image)

            if self.show_window:
                workspace.display_data.probabilities = size_corrected

        self.add_measurements(workspace)

        if self.show_window:
            if x.volumetric:
                # Can't show CellPose-accepted colour images in 3D
                workspace.display_data.x_data = x.pixel_data
            else:
                workspace.display_data.x_data = x_data
            workspace.display_data.y_data = y_data
            workspace.display_data.dimensions = dimensions

    def display(self, workspace, figure):
        if self.save_probabilities.value:
            layout = (2, 2)
        else:
            layout = (2, 1)

        figure.set_subplots(
            dimensions=workspace.display_data.dimensions, subplots=layout
        )

        figure.subplot_imshow(
            colormap="gray",
            image=workspace.display_data.x_data,
            title="Input Image",
            x=0,
            y=0,
        )

        figure.subplot_imshow_labels(
            image=workspace.display_data.y_data,
            sharexy=figure.subplot(0, 0),
            title=self.y_name.value,
            x=1,
            y=0,
        )
        if self.save_probabilities.value:
            figure.subplot_imshow(
                colormap="gray",
                image=workspace.display_data.probabilities,
                sharexy=figure.subplot(0, 0),
                title=self.probabilities_name.value,
                x=0,
                y=1,
            )

    def do_check_gpu(self):
        import importlib.util
        torch_installed = importlib.util.find_spec('torch') is not None
        if models.use_gpu(istorch=torch_installed):
            message = "GPU appears to be working correctly!"
        else:
            message = "GPU test failed. There may be something wrong with your configuration."
        import wx
        wx.MessageBox(message, caption="GPU Test")



    def upgrade_settings(self, setting_values, variable_revision_number, module_name):
        if variable_revision_number == 1:
            setting_values = setting_values+["0.4", "0.0"]
            variable_revision_number = 2
        return setting_values, variable_revision_number
