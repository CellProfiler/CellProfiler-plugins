#################################
#
# Imports from useful Python libraries
#
#################################

import numpy
import os
import skimage
import importlib.metadata
import subprocess
import uuid
import shutil
import logging
import sys
import math
import scipy.ndimage

#################################
#
# Imports from CellProfiler
#
##################################

from cellprofiler_core.image import Image
from cellprofiler_core.module.image_segmentation import ImageSegmentation
from cellprofiler_core.object import Objects
from cellprofiler_core.setting import Binary, ValidationError
from cellprofiler_core.setting.choice import Choice
from cellprofiler_core.setting.do_something import DoSomething
from cellprofiler_core.setting.subscriber import ImageSubscriber
from cellprofiler_core.preferences import get_default_output_directory
from cellprofiler_core.setting.text import (
    Integer,
    ImageName,
    Directory,
    Filename,
    Float,
)

CUDA_LINK = "https://pytorch.org/get-started/locally/"
Cellpose_link = " https://doi.org/10.1038/s41592-020-01018-x"
Omnipose_link = "https://doi.org/10.1101/2021.11.03.467199"
LOGGER = logging.getLogger(__name__)

__doc__ = f"""\
RunCellpose
===========

**RunCellpose** uses a pre-trained machine learning model (Cellpose) to detect cells or nuclei in an image.

This module is useful for automating simple segmentation tasks in CellProfiler.
The module accepts greyscale input images and produces an object set.
Probabilities can also be captured as an image.

Loading in a model will take slightly longer the first time you run it each session.
When evaluating performance you may want to consider the time taken to predict subsequent images.

This module is compatible with Omnipose, Cellpose 2, Cellpose 3, and Cellpose-SAM (4).

You can run this module using Cellpose installed to the same Python environment as CellProfiler.
See our documentation at https://plugins.cellprofiler.org/runcellpose.html for more information on installation.

Alternatively, you can run this module using Cellpose in a Docker that the module will automatically download for you so you do not have to perform any installation yourself.

On the first time loading into CellProfiler, Cellpose will need to download some model files from the internet. This
may take some time. If you want to use a GPU to run the model, you'll need a compatible version of PyTorch and a
supported GPU. Instructions are avaiable at this link: {CUDA_LINK}

Note that RunCellpose supports the Cellpose 3 functionality of using image restoration models to improve the input images before segmentation for both Docker and Python methods.
However, it only supports saving out or visualizing the intermediate restored images when using the Python method.

Stringer, C., Wang, T., Michaelos, M. et al. Cellpose: a generalist algorithm for cellular segmentation. Nat Methods 18, 100–106 (2021). {Cellpose_link}
Kevin J. Cutler, Carsen Stringer, Paul A. Wiggins, Joseph D. Mougous. Omnipose: a high-precision morphology-independent solution for bacterial cell segmentation. bioRxiv 2021.11.03.467199. {Omnipose_link}
============ ============ ===============
Supports 2D? Supports 3D? Respects masks?
============ ============ ===============
YES          YES          NO
============ ============ ===============

"""

"Select Cellpose Docker Image"
CELLPOSE_DOCKERS = {'v2': ["cellprofiler/runcellpose_no_pretrained:2.3.2",
                     "cellprofiler/runcellpose_with_pretrained:2.3.2",
                     "cellprofiler/runcellpose_with_pretrained:2.2"],
                     'v3': ["erinweisbart/cellpose:3.1.1.2"], #TODO
                     'v4': ["erinweisbart/cellpose:4.0.5"]} #TODO

"Detection mode"
MODEL_NAMES = {'v2':['cyto','nuclei','tissuenet','livecell', 'cyto2', 'general',
                'CP', 'CPx', 'TN1', 'TN2', 'TN3', 'LC1', 'LC2', 'LC3', 'LC4', 'custom'],
                'v3':[ "cyto3", "nuclei", "cyto2_cp3", "tissuenet_cp3", "livecell_cp3", "yeast_PhC_cp3",
    "yeast_BF_cp3", "bact_phase_cp3", "bact_fluor_cp3", "deepbacs_cp3", "cyto2", "cyto", "custom"],
    'v4':['cpsam','custom']}

DENOISER_NAMES = ['denoise_cyto3', 'deblur_cyto3', 'upsample_cyto3',
                  'denoise_nuclei', 'deblur_nuclei', 'upsample_nuclei']
# Only these models support size scaling for v2/v3
SIZED_MODELS = {"cyto3", "cyto2", "cyto", "nuclei"}

def get_custom_model_vars(self):
    model_file = self.model_file_name.value
    model_directory = self.model_directory.get_absolute_path()
    model_path = os.path.join(model_directory, model_file)
    return model_file, model_directory, model_path

def cleanup(self):
    # Try to clear some GPU memory for other worker processes.
    try:
        from torch import cuda
        cuda.empty_cache()
    except Exception as e:
        print(f"Unable to clear GPU memory. You may need to restart CellProfiler to change models. {e}")

class RunCellpose(ImageSegmentation):
    category = "Object Processing"

    module_name = "RunCellpose"

    variable_revision_number = 7

    doi = {
        "Please also cite Cellpose when using RunCellpose:": "https://doi.org/10.1038/s41592-020-01018-x",
        "If you are using Cellpose 2 also cite the following:": "https://doi.org/10.1038/s41592-022-01663-4",
        "If you are using Cellpose 3 also cite the following:": "https://doi.org/10.1038/s41592-025-02595-5",
        "If you are using Cellpose 4 also cite the following:": "https://doi.org/10.1101/2025.04.28.651001",
        "If you are using Omnipose also cite the following:": "https://doi.org/10.1101/2021.11.03.467199",
    }

    def create_settings(self):
        super(RunCellpose, self).create_settings()

        self.rescale = Binary(
            text="Rescale images before running Cellpose",
            value=True,
            doc="""\
Reminds the user that the  normalization step will be performed to ensure suimilar segmentation behaviour in the RunCellpose
module and the Cellpose app.
"""
        )


        self.docker_or_python = Choice(
            text="Run CellPose in docker or local python environment",
            choices=["Docker", "Python"],
            value="Docker",
            doc="""\
If Docker is selected, ensure that Docker Desktop is open and running on your
computer. On first run of the RunCellpose plugin, the Docker container will be
downloaded. However, this slow downloading process will only have to happen
once.

If Python is selected, the Python environment in which CellProfiler and Cellpose
are installed will be used.
""",
        )
        self.cellpose_version = Choice(
            text="Select Cellpose version",
            choices=['omnipose', 'v2', 'v3', 'v4'],
            value='v3',
            doc="Select the version of Cellpose you want to use.")
            
        self.docker_image_v2 = Choice(
            text="Select Cellpose docker image",
            choices=CELLPOSE_DOCKERS['v2'],
            value=CELLPOSE_DOCKERS['v2'][0],
            doc="""\
Select which Docker image to use for running Cellpose.
If you are not using a custom model, you should select a Docker image **with pretrained**. If you are using a custom model,
you can use any of the available Dockers, but those with pretrained models will be slightly larger (~500 MB).
""")
        self.docker_image_v3 = Choice(
            text="Select Cellpose docker image",
            choices=CELLPOSE_DOCKERS['v3'],
            value=CELLPOSE_DOCKERS['v3'][0],
            doc="""\
Select which Docker image to use for running Cellpose.
If you are not using a custom model, you should select a Docker image **with pretrained**. If you are using a custom model,
you can use any of the available Dockers, but those with pretrained models will be slightly larger (~500 MB).""",
        )
        self.docker_image_v4 = Choice(
            text="Select Cellpose docker image",
            choices=CELLPOSE_DOCKERS['v4'],
            value=CELLPOSE_DOCKERS['v4'][0],
            doc="""\
Select which Docker image to use for running Cellpose.
If you are not using a custom model, you should select a Docker image **with pretrained**. If you are using a custom model,
you can use any of the available Dockers, but those with pretrained models will be slightly larger (~500 MB).""",
        )

        self.specify_diameter = Binary(
            text="Specify expected object diameter?",
            value=False,
            doc="""\
Cellpose 4 was trained on images with ROI diameters from size 7.5 to 120, with a mean diameter of 30 pixels. 
Thus the model has a good amount of size-invariance, meaning that specifying the diameter is optional. 
However, you can have them downsampled by Cellpose 4 if you specify a larger diameter.
""",)
        
        self.expected_diameter = Integer(
            text="Expected object diameter",
            value=30,
            minval=0,
            doc="""\
The average diameter of the objects to be detected. 
In Cellpose 1-3, Cellpose models come with a pre-defined object diameter. Your image will be resized during detection to attempt to
match the diameter expected by the model. The default models have an expected diameter of ~16 pixels, if trying to
detect much smaller objects it may be more efficient to resize the image first using the Resize module.
If set to 0 in Cellpose 1-3, it will attempt to automatically detect object size.
Note that automatic diameter mode does not work when running on 3D images.
""",
        )

        self.mode_v2 = Choice(
            text="Detection mode",
            choices=MODEL_NAMES['v2'],
            value=MODEL_NAMES['v2'][0],
            doc="""\
CellPose comes with models for detecting nuclei or cells. Alternatively, you can supply a custom-trained model
generated using the command line or Cellpose GUI. Custom models can be useful if working with unusual cell types.
""",
        )
        self.mode_v3 = Choice(
            text="Detection mode",
            choices=MODEL_NAMES['v3'],
            value=MODEL_NAMES['v3'][0],
            doc="""\
CellPose comes with models for detecting nuclei or cells. Alternatively, you can supply a custom-trained model
generated using the command line or Cellpose GUI. Custom models can be useful if working with unusual cell types.
""",
        )
        self.mode_v4 = Choice(
            text="Detection mode",
            choices=MODEL_NAMES['v4'],
            value=MODEL_NAMES['v4'][0],
            doc="""\
CellPose comes with models for detecting nuclei or cells. Alternatively, you can supply a custom-trained model
generated using the command line or Cellpose GUI. Custom models can be useful if working with unusual cell types.
""",
        )

        self.omni = Binary(
            text="Use Omnipose for mask reconstruction",
            value=False,
            doc="""\
If enabled, use omnipose mask recontruction features will be used (Omnipose installation required and CellPose >= 1.0)  """,
        )

        self.do_3D = Binary(
            text="Use 3D",
            value=False,
            doc="""\
If enabled, 3D specific settings will be available.""",
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
""",
        )

        self.use_averaging = Binary(
            text="Use averaging",
            value=False,
            doc="""\
If enabled, CellPose will run it's 4 inbuilt models and take a consensus to determine the results. If disabled, only a
single model will be called to produce results. Disabling averaging is faster to run but less accurate.""",
        )

        self.invert = Binary(
            text="Invert images",
            value=False,
            doc="""\
If enabled the image will be inverted and also normalized. For use with fluorescence images using bact model (bact model was trained on phase images""",
        )

        self.supply_nuclei = Binary(
            text="Supply nuclei image as well?",
            value=False,
            doc="""
When detecting whole cells, you can provide a second image featuring a nuclear stain to assist
the model with segmentation. This can help to split touching cells.""",
        )

        self.nuclei_image = ImageSubscriber(
            "Select the nuclei image",
            doc="Select the image you want to use as the nuclear stain.",
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
Select the location of the pre-trained CellPose model file that will be used for detection.""",
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
This file can be generated by training a custom model withing the CellPose GUI or command line applications.""",
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
            doc="""\
The flow_threshold parameter is the maximum allowed error of the flows for each mask. The default is flow_threshold=0.4.
Increase this threshold if cellpose is not returning as many masks as you’d expect.
Similarly, decrease this threshold if cellpose is returning too many ill-shaped masks
""",
        )

        self.cellprob_threshold = Float(
            text="Cell probability threshold",
            value=0.0,
            minval=-6.0,
            maxval=6.0,
            doc=f"""\
Cell probability threshold (all pixels with probability above threshold kept for masks). Recommended default is 0.0.
Values vary from -6 to 6
""",
        )

        self.manual_GPU_memory_share = Float(
            text="GPU memory share for each worker",
            value=0.1,
            minval=0.0000001,
            maxval=1,
            doc="""\
Fraction of the GPU memory share available to each worker. Value should be set such that this number times the number
of workers in each copy of CellProfiler times the number of copies of CellProfiler running (if applicable) is <1
""",
        )

        self.stitch_threshold = Float(
            text="Stitch Threshold",
            value=0.0,
            minval=0,
            doc=f"""\
There may be additional differences in YZ and XZ slices that make them unable to be used for 3D segmentation.
In those instances, you may want to turn off 3D segmentation (do_3D=False) and run instead with stitch_threshold>0.
Cellpose will create masks in 2D on each XY slice and then stitch them across slices if the IoU between the mask on the current slice and the next slice is greater than or equal to the stitch_threshold.
""",
        )

        self.min_size = Integer(
            text="Minimum size",
            value=15,
            minval=-1,
            doc="""\
Minimum number of pixels per mask, can turn off by setting value to -1
""",
        )

        self.remove_edge_masks = Binary(
            text="Remove objects that are touching the edge?",
            value=True,
            doc="""
If you do not want to include any object masks that are not in full view in the image, you can have the masks that have pixels touching the the edges removed.
The default is set to "Yes".
""",
        )

        self.probability_rescale_setting = Binary(
            text="Rescale probability map?",
            value=True,
            doc="""
Activate to rescale probability map to 0-255 (which matches the scale used when running this module from Docker)
""",
        )
        self.denoise = Binary(
            text="Preprocess image before segmentation?",
            value=False,
            doc="""
            If enabled, a separate Cellpose model will be used to clean the input image before segmentation.
            Try this if your input images are blurred, noisy or otherwise need cleanup.
        """,
        )

        self.denoise_type = Choice(
            text="Preprocessing model",
            choices=DENOISER_NAMES,
            value=DENOISER_NAMES[0],
            doc="""\
            Model to use for preprocessing of images. An AI model can be applied to denoise, remove blur or upsample images prior to 
            segmentation. Select nucleus models for nuclei or cyto3 models for anything else.
            
            'Denoise' models may help if your staining is inconsistent.
            'Deblur' attempts to improve out-of-focus images
            'Upsample' will attempt to resize the images so that the object sizes match the native diameter of the segmentation model.
            
            N.b. for upsampling it is essential that the "Expected diameter" setting is correct for the input images
            """,
        )
        self.denoise_image = Binary(
            text="Save preprocessed image?",
            value=False,
            doc="""
            If enabled, the intermediate preprocessed image will be recorded as a new image.
            This is only supported for Python mode of Cellpose 3.
        """,
        )
        self.denoise_name = ImageName(
            "Name the preprocessed image",
            "Preprocessed",
            doc="Enter the name you want to call the preprocessed image produced by this module.",
        )

    def settings(self):
        return [
            self.x_name,
            self.rescale,
            self.docker_or_python,
            self.cellpose_version,
            self.docker_image_v2,
            self.docker_image_v3,
            self.docker_image_v4,
            self.specify_diameter,
            self.expected_diameter,
            self.mode_v2,
            self.mode_v3,
            self.mode_v4,
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
            self.cellprob_threshold,
            self.manual_GPU_memory_share,
            self.stitch_threshold,
            self.do_3D,
            self.min_size,
            self.omni,
            self.invert,
            self.remove_edge_masks,
            self.probability_rescale_setting,
            self.denoise,
            self.denoise_type,
            self.denoise_image,
            self.denoise_name,
        ]

    def visible_settings(self):
        vis_settings = [self.rescale, self.cellpose_version]

        if self.cellpose_version.value == 'omnipose': # omnipose only supports Python, not Docker
            self.docker_or_python.value = "Python"
            vis_settings += [self.omni]
        else:
            vis_settings += [self.docker_or_python]

        if self.docker_or_python.value == "Docker":
            if self.cellpose_version.value == 'v2':
                vis_settings += [self.docker_image_v2]
            elif self.cellpose_version.value == 'v3':
                vis_settings += [self.docker_image_v3]
            elif self.cellpose_version.value == 'v4':
                vis_settings += [self.docker_image_v4]
        
        if self.cellpose_version.value == 'v2':
            vis_settings += [self.mode_v2]
            self.mode = self.mode_v2
        elif self.cellpose_version.value == 'v3':
            vis_settings += [self.mode_v3]
            self.mode = self.mode_v3
        elif self.cellpose_version.value == 'v4':
            vis_settings += [self.mode_v4]
            self.mode = self.mode_v4

        vis_settings += [self.x_name]

        if self.mode.value != "nuclei":
            vis_settings += [self.supply_nuclei]
            if self.supply_nuclei.value:
                vis_settings += [self.nuclei_image]
        if self.mode.value == "custom":
            vis_settings += [
                self.model_directory,
                self.model_file_name,
            ]
        if self.cellpose_version.value == 'v4':
            vis_settings += [self.specify_diameter]
        if self.specify_diameter.value:
            vis_settings += [self.expected_diameter]

        vis_settings += [
            self.cellprob_threshold,
            self.min_size,
            self.flow_threshold,
            self.y_name,
            self.save_probabilities,
        ]
        if self.save_probabilities.value:
            vis_settings += [self.probabilities_name]
            if self.docker_or_python.value == 'Python':
                vis_settings += [self.probability_rescale_setting]

        if self.cellpose_version.value in ['v2','v3']:
            vis_settings += [self.invert]

        vis_settings += [self.do_3D, self.stitch_threshold, self.remove_edge_masks]

        if self.do_3D.value:
            vis_settings.remove(self.stitch_threshold)

        vis_settings += [self.use_averaging, self.use_gpu]

        if self.docker_or_python.value == 'Python':
            if self.use_gpu.value:
                vis_settings += [self.gpu_test, self.manual_GPU_memory_share]

        if self.cellpose_version.value == 'v3':
            vis_settings += [self.denoise]
            if self.denoise.value:
                vis_settings += [self.denoise_type, self.denoise_image]
                if self.denoise_image.value:
                    vis_settings += [self.denoise_name]

        return vis_settings

    def validate_module(self, pipeline):
        if self.docker_or_python.value == "Python":
            """If using custom model, validate the model file opens and works"""
            from cellpose import models
            if self.mode.value == "custom":
                model_file = self.model_file_name.value
                model_directory = self.model_directory.get_absolute_path()
                model_path = os.path.join(model_directory, model_file)
                try:
                    open(model_path)
                except:
                    raise ValidationError(
                        "Failed to load custom file: %s " % model_path,
                        self.model_file_name,
                    )
                try:
                    model = models.CellposeModel(pretrained_model=model_path, gpu=self.use_gpu.value)
                except:
                    raise ValidationError(
                        "Failed to load custom model: %s "
                        % model_path, self.model_file_name,
                    )

    def run(self, workspace):
        x_name = self.x_name.value
        y_name = self.y_name.value
        images = workspace.image_set
        x = images.get_image(x_name)
        dimensions = x.dimensions
        x_data = x.pixel_data

        if self.cellpose_version.value == 'omnipose':
            self.mode = self.mode_v2
            self.denoise.value = False  # Denoising only supported in v3
        if self.cellpose_version.value == 'v2':
            self.mode = self.mode_v2
            self.docker_image = self.docker_image_v2
            self.denoise.value = False  # Denoising only supported in v3
        elif self.cellpose_version.value == 'v3':
            self.mode = self.mode_v3
            self.docker_image = self.docker_image_v3
        elif self.cellpose_version.value == 'v4':
            self.mode = self.mode_v4
            self.docker_image = self.docker_image_v4
            self.denoise.value = False  # Denoising only supported in v3

        if self.rescale.value:
            rescale_x = x_data.copy()
            x01 = numpy.percentile(rescale_x, 1)
            x99 = numpy.percentile(rescale_x, 99)
            x_data = numpy.clip((rescale_x - x01) / (x99 - x01), a_min=0, a_max=1)

        anisotropy = 0.0
        if self.do_3D.value:
            anisotropy = x.spacing[0] / x.spacing[1]

        if self.specify_diameter.value:
            diam = self.expected_diameter.value if self.expected_diameter.value > 0 else None

        if x.multichannel:
            raise ValueError(
                "Color images are not currently supported. Please provide greyscale images."
            )

        if self.mode.value != "nuclei" and self.supply_nuclei.value:
            nuc_image = images.get_image(self.nuclei_image.value)
            # CellPose 1-3 expects RGB, we'll have a blank red channel, cells in green and nuclei in blue.
            if self.do_3D.value:
                x_data = numpy.stack(
                    (numpy.zeros_like(x_data), x_data, nuc_image.pixel_data), axis=1
                )

            else:
                x_data = numpy.stack(
                    (numpy.zeros_like(x_data), x_data, nuc_image.pixel_data), axis=-1
                )

            channels = [2, 3]
        else:
            channels = [0, 0]

        if self.docker_or_python.value == "Python":
            from cellpose import models, io, core, utils
            self.cellpose_ver = importlib.metadata.version('cellpose')

            if self.cellpose_version.value == 'omnipose':
                assert int(self.cellpose_ver[0])<2, "Cellpose version selected in RunCellpose module doesn't match version in Python"
                assert float(self.cellpose_ver[0:3]) >= 0.6, "Cellpose v1/omnipose requires Cellpose >= 0.6"
                if self.mode.value != 'custom':
                    model = models.Cellpose(model_type= self.mode.value,
                                            gpu=self.use_gpu.value)
                else:
                    model_file, model_directory, model_path = get_custom_model_vars(self)
                    model = models.CellposeModel(pretrained_model=model_path, gpu=self.use_gpu.value)

                if self.use_gpu.value and model.torch:
                    from torch import cuda
                    cuda.set_per_process_memory_fraction(self.manual_GPU_memory_share.value)

                try:
                    y_data, flows, *_ = model.eval(
                        x_data,
                        channels=channels,
                        diameter=diam,
                        net_avg=self.use_averaging.value,
                        do_3D=self.do_3D.value,
                        anisotropy=anisotropy,
                        flow_threshold=self.flow_threshold.value,
                        cellprob_threshold=self.cellprob_threshold.value,
                        stitch_threshold=self.stitch_threshold.value, # is ignored if do_3D=True
                        min_size=self.min_size.value,
                        omni=self.omni.value,
                        invert=self.invert.value,
                )
                except Exception as a:
                            print(f"Unable to create masks. Check your module settings. {a}")
                finally:
                    if self.use_gpu.value and model.torch:
                        cleanup(self)
                        
            if self.cellpose_version.value == 'v2':
                assert int(self.cellpose_ver[0])==2, "Cellpose version selected in RunCellpose module doesn't match version in Python"
                if self.mode.value != 'custom':
                    model = models.CellposeModel(model_type= self.mode.value,
                                            gpu=self.use_gpu.value)
                else:
                    model_file, model_directory, model_path = get_custom_model_vars(self)
                    model = models.CellposeModel(pretrained_model=model_path, gpu=self.use_gpu.value)

                if self.use_gpu.value and model.torch:
                    from torch import cuda
                    cuda.set_per_process_memory_fraction(self.manual_GPU_memory_share.value)

                try:
                        y_data, flows, *_ = model.eval(
                            x_data,
                            channels=channels,
                            diameter=diam,
                            net_avg=self.use_averaging.value,
                            do_3D=self.do_3D.value,
                            anisotropy=anisotropy,
                            flow_threshold=self.flow_threshold.value,
                            cellprob_threshold=self.cellprob_threshold.value,
                            stitch_threshold=self.stitch_threshold.value, # is ignored if do_3D=True
                            min_size=self.min_size.value,
                            invert=self.invert.value,
                    )
                except Exception as a:
                            print(f"Unable to create masks. Check your module settings. {a}")
                finally:
                    if self.use_gpu.value and model.torch:
                        cleanup(self)

            elif self.cellpose_version.value == 'v3':
                assert int(self.cellpose_ver[0])==3, "Cellpose version selected in RunCellpose module doesn't match version in Python"
                if self.mode.value == 'custom':
                    model_file, model_directory, model_path  = get_custom_model_vars(self)
                model_params = (self.mode.value, self.use_gpu.value)
                LOGGER.info(f"Loading new model: {self.mode.value}")
                if self.mode.value in SIZED_MODELS:
                    self.current_model = models.Cellpose(
                        model_type=self.mode.value, gpu=self.use_gpu.value)
                else:
                    self.current_model = models.CellposeModel(
                        model_type=self.mode.value, gpu=self.use_gpu.value)
                self.current_model_params = model_params

                if self.use_gpu.value:
                    try:
                        from torch import cuda
                        cuda.set_per_process_memory_fraction(self.manual_GPU_memory_share.value)
                    except:
                        print(
                            "Failed to set GPU memory share. Please check your PyTorch installation. Not setting per-process memory share."
                        )

                if self.denoise.value:
                    from cellpose import denoise
                    recon_params = (
                        self.denoise_type.value,
                        self.use_gpu.value,
                        self.mode.value != "nuclei" and self.supply_nuclei.value
                    )
                    self.recon_model = denoise.DenoiseModel(
                        model_type=recon_params[0],
                        gpu=recon_params[1],
                        chan2=recon_params[2]
                    )
                    if self.recon_model is not None:
                        input_data = self.recon_model.eval(
                            x_data,
                            diameter=diam,
                            channels=channels
                        )
                        # Upsampling models scale object diameter to a target size
                        if self.denoise_type.value == "upsample_cyto3":
                            diam = 30
                        elif self.denoise_type.value == "upsample_nuclei":
                            diam = 17
                        # Result only includes input channels
                        if self.mode.value != "nuclei" and self.supply_nuclei.value:
                            channels = [0, 1]
                else:
                    input_data = x_data
                
                try:
                    y_data, flows, *_ = self.current_model.eval(
                        input_data,
                        channels=channels,
                        diameter=diam,
                        do_3D=self.do_3D.value,
                        anisotropy=anisotropy,
                        flow_threshold=self.flow_threshold.value,
                        cellprob_threshold=self.cellprob_threshold.value,
                        stitch_threshold=self.stitch_threshold.value, # is ignored if do_3D=True
                        min_size=self.min_size.value,
                        invert=self.invert.value,
                    )

                    if self.denoise.value and "upsample" in self.denoise_type.value:
                        y_data = skimage.transform.resize(y_data, x.pixel_data.shape,
                                                        preserve_range=True, order=0)

                except Exception as a:
                            print(f"Unable to create masks. Check your module settings. {a}")
                finally:
                    if self.use_gpu.value:
                        cleanup(self)

            elif self.cellpose_version.value == 'v4':
                assert int(self.cellpose_ver[0])==4, "Cellpose version selected in RunCellpose module doesn't match version in Python"
                if self.mode.value == 'custom':
                    model_file, model_directory, model_path  = get_custom_model_vars(self)
                model_params = (self.mode.value, self.use_gpu.value)
                LOGGER.info(f"Loading new model: {self.mode.value}")
                self.current_model = models.CellposeModel(gpu=self.use_gpu.value)
                self.current_model_params = model_params

                if self.use_gpu.value:
                    try:
                        from torch import cuda
                        cuda.set_per_process_memory_fraction(self.manual_GPU_memory_share.value)
                    except:
                        print(
                            "Failed to set GPU memory share. Please check your PyTorch installation. Not setting per-process memory share."
                        )

                if self.specify_diameter.value:
                    try:
                        y_data, flows, *_ = self.current_model.eval(
                            x_data,
                            diameter=diam,
                            do_3D=self.do_3D.value,
                            anisotropy=anisotropy,
                            flow_threshold=self.flow_threshold.value,
                            cellprob_threshold=self.cellprob_threshold.value,
                            stitch_threshold=self.stitch_threshold.value, # is ignored if do_3D=True
                            min_size=self.min_size.value,
                            invert=self.invert.value,
                        )

                    except Exception as a:
                                print(f"Unable to create masks. Check your module settings. {a}")
                    finally:
                        if self.use_gpu.value and model.torch:
                            cleanup(self)
                else:
                    try:
                        y_data, flows, *_ = self.current_model.eval(
                            x_data,
                            do_3D=self.do_3D.value,
                            anisotropy=anisotropy,
                            flow_threshold=self.flow_threshold.value,
                            cellprob_threshold=self.cellprob_threshold.value,
                            stitch_threshold=self.stitch_threshold.value, # is ignored if do_3D=True
                            min_size=self.min_size.value,
                            invert=self.invert.value,
                        )

                    except Exception as a:
                                print(f"Unable to create masks. Check your module settings. {a}")
                    finally:
                        if self.use_gpu.value:
                            cleanup(self)

            if self.remove_edge_masks:
                y_data = utils.remove_edge_masks(y_data)

        elif self.docker_or_python.value == "Docker":
            # Define how to call docker
            docker_path = "docker" if sys.platform.lower().startswith("win") else "/usr/local/bin/docker"
            # Create a UUID for this run
            unique_name = str(uuid.uuid4())
            # Directory that will be used to pass images to the docker container
            temp_dir = os.path.join(get_default_output_directory(), ".cellprofiler_temp", unique_name)
            temp_img_dir = os.path.join(temp_dir, "img")
            
            os.makedirs(temp_dir, exist_ok=True)
            os.makedirs(temp_img_dir, exist_ok=True)

            temp_img_path = os.path.join(temp_img_dir, unique_name+".tiff")
            if self.mode.value == "custom":
                model_file, model_directory, model_path = get_custom_model_vars(self)
                model = models.CellposeModel(pretrained_model=model_path, gpu=self.use_gpu.value)
                
                temp_model_dir = os.path.join(temp_dir, "model")
                os.makedirs(temp_model_dir, exist_ok=True)
                # Copy the model
                shutil.copy(model_path, os.path.join(temp_model_dir, model_file))

            # Save the image to the Docker mounted directory
            skimage.io.imsave(temp_img_path, x_data)

            cmd = [docker_path, 'run', '--rm', '-v', f'{temp_dir}:/data', self.docker_image.value]
            if self.use_gpu.value:
                cmd += ['--gpus', 'all']
            cmd += ['cellpose', '--verbose', '--dir', '/data/img', '--pretrained_model']
            if self.mode.value !='custom':
                cmd += [self.mode.value]
            else:
                cmd += ['/data/model/' + model_file]
            if self.cellpose_version.value == 'v3':
                if self.denoise.value:
                    cmd += ['--restore_type', self.denoise_type.value]
            if self.cellpose_version.value in ['v2','v3']:
                cmd += ['--chan', str(channels[0]), '--chan2', str(channels[1]), '--diameter', str(diam)] 
            if self.cellpose_version.value in ['v4']:
                if self.specify_diameter.value:
                    cmd += ['--diameter', str(diam)]
            if self.use_averaging.value:
                cmd += ['--net_avg']
            if self.do_3D.value:
                cmd += ['--do_3D']
            cmd += ['--anisotropy', str(anisotropy), '--flow_threshold', str(self.flow_threshold.value), '--cellprob_threshold', 
                    str(self.cellprob_threshold.value), '--stitch_threshold', str(self.stitch_threshold.value), '--min_size', str(self.min_size.value)]
            if self.cellpose_version.value in ['v2','v3']:
                if self.invert.value:
                    cmd += ['--invert']
            if self.remove_edge_masks.value:
                cmd += ['--exclude_on_edges']
            print(cmd)
            try:
                subprocess.run(cmd, text=True)
                cellpose_output = numpy.load(os.path.join(temp_img_dir, unique_name + "_seg.npy"), allow_pickle=True).item()
                y_data = cellpose_output["masks"]
                flows = cellpose_output["flows"]
            finally:      
                # Delete the temporary files
                try:
                    shutil.rmtree(temp_dir)
                except:
                    LOGGER.error("Unable to delete temporary directory, files may be in use by another program.")
                    LOGGER.error("Temp folder is subfolder {tempdir} in your Default Output Folder.\nYou may need to remove it manually.")


        y = Objects()
        y.segmented = y_data
        y.parent_image = x.parent_image
        objects = workspace.object_set
        objects.add_objects(y, y_name)
        object_count = y.count

        if self.denoise.value and self.show_window:
            # Need to remove unnecessary extra axes
            denoised_image = numpy.squeeze(input_data)
            if "upsample" in self.denoise_type.value:
                denoised_image = skimage.transform.resize(
                    denoised_image, x_data.shape)
            workspace.display_data.denoised_image = denoised_image

        if self.save_probabilities.value:
            if self.docker_or_python.value == "Docker":
                # get rid of extra dimension
                prob_map = numpy.squeeze(flows[1], axis=0) # ranges 0-255
            else:
                prob_map = flows[2]
                rescale_prob_map = prob_map.copy()
                prob_map01 = numpy.percentile(rescale_prob_map, 1)
                prob_map99 = numpy.percentile(rescale_prob_map, 99)
                prob_map = numpy.clip((rescale_prob_map - prob_map01) / (prob_map99 - prob_map01), a_min=0, a_max=1)
            # Flows come out sized relative to CellPose's inbuilt model size.
            # We need to slightly resize to match the original image.
            size_corrected = skimage.transform.resize(prob_map, y_data.shape)
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

            workspace.display_data.primary_labels = y.segmented

            workspace.display_data.statistics = []
            statistics = workspace.display_data.statistics
            statistics.append(["# of accepted objects", "%d" % object_count])
            
            if object_count > 0:
                areas = y.areas
                areas.sort()
                low_diameter = (
                    math.sqrt(float(areas[object_count // 10]) / numpy.pi) * 2
                )
                median_diameter = (
                    math.sqrt(float(areas[object_count // 2]) / numpy.pi) * 2
                )
                high_diameter = (
                    math.sqrt(float(areas[object_count * 9 // 10]) / numpy.pi) * 2
                )
                statistics.append(
                    ["10th pctile diameter", "%.1f pixels" % low_diameter]
                )
                statistics.append(["Median diameter", "%.1f pixels" % median_diameter])
                statistics.append(
                    ["90th pctile diameter", "%.1f pixels" % high_diameter]
                )
                object_area = numpy.sum(areas)
                total_area = numpy.product(y_data.shape[:2])
                statistics.append(
                    [
                        "Area covered by objects",
                        "%.1f %%" % (100.0 * float(object_area) / float(total_area)),
                    ]
                )

    def display(self, workspace, figure):
        if self.save_probabilities.value or self.denoise.value:
            layout = (3, 2)
        else:
            layout = (2, 2)

        figure.set_subplots(subplots=layout)
        
        title = "Input image, cycle #%d" % (workspace.measurements.image_number,)
        figure.subplot_imshow(
            colormap="gray",
            image=workspace.display_data.x_data,
            title=title,
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
        
        cplabels = [
                dict(name=self.y_name.value, labels=[workspace.display_data.primary_labels]),
            ]

        title = "%s outlines" % self.y_name.value
        figure.subplot_imshow_grayscale(
            0, 1, workspace.display_data.x_data, title, cplabels=cplabels, sharexy=figure.subplot(0, 0),
        )

        figure.subplot_table(
            1,
            1,
            [[x[1]] for x in workspace.display_data.statistics],
            row_labels=[x[0] for x in workspace.display_data.statistics],
        )
        
        if self.save_probabilities.value:
            figure.subplot_imshow(
                colormap="gray",
                image=workspace.display_data.probabilities,
                sharexy=figure.subplot(0, 0),
                title=self.probabilities_name.value,
                x=2,
                y=0,
            )
        if self.denoise.value:
            figure.subplot_imshow(
                colormap="gray",
                image=workspace.display_data.denoised_image,
                sharexy=figure.subplot(0, 0),
                title=self.denoise_name.value,
                x=2,
                y=1,
            )

    def do_check_gpu(self):
        import importlib.util
        from cellpose import core
        torch_installed = importlib.util.find_spec('torch') is not None
        self.cellpose_ver = importlib.metadata.version('cellpose')
        #if the old version of cellpose <2.0, then use istorch kwarg
        if float(self.cellpose_ver[0:3]) >= 0.7 and int(self.cellpose_ver[0])<2:
            GPU_works = core.use_gpu(istorch=torch_installed)
        else:  # if new version of cellpose, use use_torch kwarg
            GPU_works = core.use_gpu(use_torch=torch_installed)
        if GPU_works:
            message = "GPU appears to be working correctly!"
        else:
            message = (
                "GPU test failed. There may be something wrong with your configuration."
            )
        import wx

        wx.MessageBox(message, caption="GPU Test")

    def upgrade_settings(self, setting_values, variable_revision_number, module_name):
        if variable_revision_number == 1:
            setting_values = setting_values + ["0.4", "0.0"]
            variable_revision_number = 2
        if variable_revision_number == 2:
            setting_values = setting_values + ["0.0", False, "15", "1.0", False, False]
            variable_revision_number = 3
        if variable_revision_number == 3:
            setting_values = [setting_values[0]] + ["Python",CELLPOSE_DOCKERS['v2'][0]] + setting_values[1:]
            variable_revision_number = 4
        if variable_revision_number == 4:
            setting_values = [setting_values[0]] + ['No'] + setting_values[1:]
            variable_revision_number = 5
        if variable_revision_number == 5:
            setting_values = setting_values + [False]
            variable_revision_number = 6
        if variable_revision_number == 6:
            new_setting_values = setting_values[0:2]
            new_setting_values += ['v3', setting_values[2], CELLPOSE_DOCKERS['v3'][0], CELLPOSE_DOCKERS['v4'][0], setting_values[3]]
            new_setting_values += [False, setting_values[4], MODEL_NAMES['v3'][0], MODEL_NAMES['v4'][0]]
            new_setting_values += [setting_values[5:], False, DENOISER_NAMES[0], False, "Preprocessed"]
            setting_values = new_setting_values
            variable_revision_number = 7
        return setting_values, variable_revision_number
    

