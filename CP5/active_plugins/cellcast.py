import os
import pathlib
from textwrap import dedent

from cellprofiler_core.module.image_segmentation import ImageSegmentation
from cellprofiler_core.object import Objects
from cellprofiler_core.setting import Binary
from cellprofiler_core.setting.choice import Choice
from cellprofiler_core.setting.text import Directory, Filename, Float
from cellprofiler_core.utilities.appose import (
    close_service,
    get_service,
    run_python_task,
)

__doc__ = """\
RunCellcast
===========

**RunCellcast** uses pre-trained StarDist models, via the
`cellcast <https://github.com/uw-loci/cellcast>`__ project, to detect cells or
nuclei in an image and produce an object set.

Unlike most other machine-learning-backed plugins, RunCellcast does not
require installing any heavy dependencies (PyTorch, TensorFlow, etc.) into
CellProfiler's own environment. Instead, the segmentation model runs in a
separate, plugin-managed Python environment launched on demand via
`Appose <https://docs.apposed.org>`__. The first run in a session will take
longer, since the environment and the pre-trained model weights both need to
be downloaded.

|

============ ============ ===============
Supports 2D? Supports 3D? Respects masks?
============ ============ ===============
YES          YES          NO
============ ============ ===============

"""

_PLUGIN_DIR = pathlib.Path(__file__).parent / "cellcast"
_ENV_SPEC = _PLUGIN_DIR / "pixi.toml"
_WORKER_SCRIPT = dedent(
    """
    import appose
    import numpy
    from cellcast_worker import predict

    _data = numpy.array(x_data.ndarray())

    _labels = predict(_data, model, weights_path, gpu, prob_threshold, nms_threshold, anisotropy)

    _labels_ndarray = appose.NDArray(dtype=_labels.dtype.name, shape=list(_labels.shape))
    _labels_ndarray.ndarray()[:] = _labels

    task.outputs['labels'] = _labels_ndarray
    """
)

MODEL_FLUO_2D = "2D (fluorescence)"
MODEL_HE_2D = "2D (H&E)"
MODEL_FLUO_3D = "3D (fluorescence)"

_MODEL_KEYS = {
    MODEL_FLUO_2D: "stardist2d_fluo",
    MODEL_HE_2D: "stardist2d_he",
    MODEL_FLUO_3D: "stardist3d_fluo",
}


class RunCellcast(ImageSegmentation):
    category = "Object Processing"

    module_name = "RunCellcast"

    variable_revision_number = 1

    # Declares this plugin as Appose-backed: the plugins dialog uses this to
    # show a distinct icon and offer a "Build Environment" button that
    # prebuilds/warms this spec via the same cache run() itself hits.
    appose_env_spec = _ENV_SPEC

    doi = {
        "Please cite the following when using RunCellcast's StarDist2D model:": "https://doi.org/10.1007/978-3-030-00934-2_30",
        "If you are using the StarDist3D model also cite the following:": "https://doi.org/10.1109/WACV45572.2020.9093435",
    }

    def create_settings(self):
        super(RunCellcast, self).create_settings()

        self.model = Choice(
            text="Model",
            choices=[MODEL_FLUO_2D, MODEL_HE_2D, MODEL_FLUO_3D],
            value=MODEL_FLUO_2D,
            doc="""\
The StarDist model to run:

- *%(MODEL_FLUO_2D)s*: expects a single-channel 2D fluorescence (or similar
  greyscale) image.
- *%(MODEL_HE_2D)s*: expects a 2D color image, such as a brightfield H&E stain.
- *%(MODEL_FLUO_3D)s*: expects a single-channel volumetric (Z-stack)
  fluorescence image.
"""
            % globals(),
        )

        self.use_gpu = Binary(
            text="Use GPU?",
            value=True,
            doc="""\
If enabled, the model runs on the GPU (via Appose's WebGPU-backed cellcast
environment) if compatible hardware is available. Otherwise, the model runs
on the CPU.""",
        )

        self.use_custom_weights = Binary(
            text="Use custom weights?",
            value=False,
            doc="""\
If enabled, weights from a custom-trained model are used instead of
cellcast's pre-trained weights. Custom weights must be in cellcast's
burnpack (``.bpk``) format.""",
        )

        self.weights_directory = Directory(
            "Location of the custom weights file",
            doc="""\
*(Used only if "Use custom weights?" is enabled)*

Select the folder containing your custom-trained weights file.""",
        )

        def get_directory_fn():
            return self.weights_directory.get_absolute_path()

        def set_directory_fn(path):
            dir_choice, custom_path = self.weights_directory.get_parts_from_path(path)

            self.weights_directory.join_parts(dir_choice, custom_path)

        self.weights_file_name = Filename(
            "Custom weights file name",
            "weights.bpk",
            get_directory_fn=get_directory_fn,
            set_directory_fn=set_directory_fn,
            exts=[("Burnpack weights (*.bpk)", "*.bpk")],
            doc="""\
*(Used only if "Use custom weights?" is enabled)*

The custom-trained weights file, in cellcast's burnpack (``.bpk``) format.""",
        )

        self.prob_thresh = Float(
            text="Probability threshold",
            value=0.5,
            minval=0.0,
            maxval=1.0,
            doc="""\
The object/polygon (or polyhedron, for the 3D model) probability threshold:
pixels with a probability above this value are used to create masks.""",
        )

        self.nms_thresh = Float(
            text="Overlap threshold",
            value=0.3,
            minval=0.0,
            maxval=1.0,
            doc="""\
The non-maximum suppression (NMS) threshold, used to prevent overlapping
object detections.""",
        )

        self.anisotropy_z = Float(
            text="Anisotropy (Z)",
            value=2.0,
            minval=0.0,
            doc="""\
*(Used only by the %(MODEL_FLUO_3D)s model)*

The Z-axis anisotropy that the model was trained with, relative to the Y and
X axes."""
            % globals(),
        )

        self.anisotropy_y = Float(
            text="Anisotropy (Y)",
            value=1.0,
            minval=0.0,
            doc="""\
*(Used only by the %(MODEL_FLUO_3D)s model)*

The Y-axis anisotropy that the model was trained with."""
            % globals(),
        )

        self.anisotropy_x = Float(
            text="Anisotropy (X)",
            value=1.0,
            minval=0.0,
            doc="""\
*(Used only by the %(MODEL_FLUO_3D)s model)*

The X-axis anisotropy that the model was trained with."""
            % globals(),
        )

    def settings(self):
        return [
            self.x_name,
            self.model,
            self.y_name,
            self.use_gpu,
            self.use_custom_weights,
            self.weights_directory,
            self.weights_file_name,
            self.prob_thresh,
            self.nms_thresh,
            self.anisotropy_z,
            self.anisotropy_y,
            self.anisotropy_x,
        ]

    def visible_settings(self):
        vis_settings = [self.x_name, self.model, self.y_name, self.use_gpu]

        vis_settings += [self.use_custom_weights]
        if self.use_custom_weights.value:
            vis_settings += [self.weights_directory, self.weights_file_name]

        vis_settings += [self.prob_thresh, self.nms_thresh]

        if self.model.value == MODEL_FLUO_3D:
            vis_settings += [self.anisotropy_z, self.anisotropy_y, self.anisotropy_x]

        return vis_settings

    def run(self, workspace):
        x = workspace.image_set.get_image(self.x_name.value)
        dimensions = x.dimensions
        x_data = x.pixel_data

        model = self.model.value

        if model == MODEL_FLUO_2D and (x.volumetric or x.multichannel):
            raise ValueError(
                "The %s model requires a single-channel 2D image." % MODEL_FLUO_2D
            )
        if model == MODEL_HE_2D and (x.volumetric or not x.multichannel):
            raise ValueError(
                "The %s model requires a multichannel (color) 2D image." % MODEL_HE_2D
            )
        if model == MODEL_FLUO_3D and not x.volumetric:
            raise ValueError(
                "The %s model requires a volumetric (Z-stack) image." % MODEL_FLUO_3D
            )

        if self.use_custom_weights.value:
            weights_path = os.path.join(
                self.weights_directory.get_absolute_path(),
                self.weights_file_name.value,
            )
        else:
            weights_path = None

        service = get_service(_ENV_SPEC).import_library("cellcast_worker", path = _PLUGIN_DIR / "_worker.py")
        outputs = run_python_task(
            _WORKER_SCRIPT,
            service=service,
            inputs={
                "x_data": x_data,
                "model": _MODEL_KEYS[model],
                "weights_path": weights_path,
                "gpu": self.use_gpu.value,
                "prob_threshold": self.prob_thresh.value,
                "nms_threshold": self.nms_thresh.value,
                "anisotropy": [
                    self.anisotropy_z.value,
                    self.anisotropy_y.value,
                    self.anisotropy_x.value,
                ],
            },
        )
        y_data = outputs["labels"]

        y = Objects()
        y.segmented = y_data
        y.parent_image = x.parent_image
        workspace.object_set.add_objects(y, self.y_name.value)

        self.add_measurements(workspace)

        if self.show_window:
            workspace.display_data.x_data = x_data
            workspace.display_data.y_data = y_data
            workspace.display_data.dimensions = dimensions

    def post_run(self, workspace):
        # Best-effort: shuts down the persistent worker process/loaded model
        # promptly at the end of a headless run or a GUI analysis's main
        # process, instead of leaving it (and e.g. a loaded GPU model)
        # sitting around until CellProfiler itself exits. This hook isn't
        # reached in a GUI run's worker subprocesses (where run() above
        # actually executes, and where the service therefore actually
        # lives) - there, `close_service()`'s own atexit registration
        # handles it instead.
        close_service(_ENV_SPEC)
