import logging

from cellprofiler_core.image import Image
from cellprofiler_core.module.image_segmentation import ImageSegmentation
from cellprofiler_core.object import Objects
from cellprofiler_core.setting.choice import Choice
from cellprofiler_core.preferences import get_default_output_directory

LOGGER = logging.getLogger(__name__)

__doc__ = f"""\
CrashDocker
===========

**CrashDocker** crashes docker

============ ============ ===============
Supports 2D? Supports 3D? Respects masks?
============ ============ ===============
YES          YES          NO
============ ============ ===============

"""

class CrashDocker(ImageSegmentation):
    category = "Object Processing"

    module_name = "CrashDocker"

    variable_revision_number = 1


    def create_settings(self):
        super(CrashDocker, self).create_settings()

        self.docker_or_python = Choice(
            text="Run in docker or local python environment",
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
        
        self.do_crash = Choice(
            text="Crash the run",
            choices=["Yes", "No"],
            value="Yes",
            doc="""\
Cause this module to crash or succeed
""",
        )

    def settings(self):
        return [
            self.x_name,
            self.docker_or_python,
            self.do_crash,
        ]

    def visible_settings(self):
        vis_settings = super.visible_settings() + [self.docker_or_python, self.do_crash]

        return vis_settings

    def run(self, workspace):
        x_name = self.x_name.value
        y_name = self.y_name.value
        images = workspace.image_set
        x = images.get_image(x_name)
        dimensions = x.dimensions
        x_data = x.pixel_data

        if self.docker_or_python.value == "Python":
            raise Exception("I am crashing")

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
                model_file = self.model_file_name.value
                model_directory = self.model_directory.get_absolute_path()
                model_path = os.path.join(model_directory, model_file)
                temp_model_dir = os.path.join(temp_dir, "model")

                os.makedirs(temp_model_dir, exist_ok=True)
                # Copy the model
                shutil.copy(model_path, os.path.join(temp_model_dir, model_file))

            # Save the image to the Docker mounted directory
            skimage.io.imsave(temp_img_path, x_data)

            cmd = f"""
            {docker_path} run --rm -v {temp_dir}:/data
            {self.docker_image.value}
            {'--gpus all' if self.use_gpu.value else ''}
            cellpose
            --dir /data/img
            {'--pretrained_model ' + self.mode.value if self.mode.value != 'custom' else '--pretrained_model /data/model/' + model_file}
            --chan {channels[0]}
            --chan2 {channels[1]}
            --diameter {diam}
            {'--net_avg' if self.use_averaging.value else ''}
            {'--do_3D' if self.do_3D.value else ''}
            --anisotropy {anisotropy}
            --flow_threshold {self.flow_threshold.value}
            --cellprob_threshold {self.cellprob_threshold.value}
            --stitch_threshold {self.stitch_threshold.value}
            --min_size {self.min_size.value}
            {'--invert' if self.invert.value else ''}
            {'--exclude_on_edges' if self.remove_edge_masks.value else ''}
            --verbose
            """

            try:
                subprocess.run(cmd.split(), text=True)
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
            setting_values = [setting_values[0]] + ["Python",CELLPOSE_DOCKER_IMAGE_WITH_PRETRAINED] + setting_values[1:]
            variable_revision_number = 4
        if variable_revision_number == 4:
            setting_values = [setting_values[0]] + ['No'] + setting_values[1:]
            variable_revision_number = 5
        if variable_revision_number == 5:
            setting_values = setting_values + [False]
            variable_revision_number = 6
        return setting_values, variable_revision_number
    

