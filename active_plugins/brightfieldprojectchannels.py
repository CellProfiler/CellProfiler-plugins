import numpy
import scipy.ndimage
from cellprofiler_core.image import Image
from cellprofiler_core.module import Module
from cellprofiler_core.setting import SettingsGroup, HiddenCount
from cellprofiler_core.setting.do_something import DoSomething, RemoveSettingButton
from cellprofiler_core.setting.subscriber import ImageSubscriber
from cellprofiler_core.setting.text import ImageName

class BrightfieldProjectChannels(Module):
    module_name = "BrightfieldProjectChannels"
    variable_revision_number = 1
    category = "Image Processing"

    def create_settings(self):
        self.output_image_name = ImageName(
            "Name the output image",
            "BrightfieldProjected",
            doc="Enter a name for the resulting projected image."
        )

        self.stack_channels = []
        self.stack_channel_count = HiddenCount(self.stack_channels)
        self.add_stack_channel_cb(can_remove=False)
        
        self.add_stack_channel = DoSomething(
            "Add another image",
            "Add another image",
            self.add_stack_channel_cb
        )

    def add_stack_channel_cb(self, can_remove=True):
        group = SettingsGroup()
        group.append("image_name", ImageSubscriber("Select image", "None"))
        if can_remove:
            group.append("remover", RemoveSettingButton("", "Remove", self.stack_channels, group))
        self.stack_channels.append(group)

    def settings(self):
        result = [self.output_image_name, self.stack_channel_count]
        for stack_channel in self.stack_channels:
            result += [stack_channel.image_name]
        return result

    def visible_settings(self):
        result = [self.output_image_name]
        for sc_group in self.stack_channels:
            result.append(sc_group.image_name)
            if hasattr(sc_group, "remover"):
                result.append(sc_group.remover)
        result.append(self.add_stack_channel)
        return result

    def prepare_settings(self, setting_values):
        try:
            num_stack_images = int(setting_values[1])
        except (ValueError, IndexError):
            num_stack_images = 1
        del self.stack_channels[num_stack_images:]
        while len(self.stack_channels) < num_stack_images:
            self.add_stack_channel_cb()

    def run(self, workspace):
        image_list = []
        for group in self.stack_channels:
            img_name = group.image_name.value
            data = workspace.image_set.get_image(img_name).pixel_data
            image_list.append(data)

        if not image_list:
            return

        stack = numpy.array(image_list)

        # 1. Local Variance (3x3)
        def get_cp_variance(img):
            mean = scipy.ndimage.uniform_filter(img, size=3)
            sq_mean = scipy.ndimage.uniform_filter(img**2, size=3)
            return sq_mean - mean**2

        variances = numpy.array([get_cp_variance(img) for img in stack])

        # 2. Gaussian Smoothing (Sigma=1.0)
        smoothed_variances = numpy.array([
            scipy.ndimage.gaussian_filter(v, sigma=1.0) for v in variances
        ])

        # 3. Find best focus indices
        best_indices = numpy.argmax(smoothed_variances, axis=0)

        # 4. Extract winning pixels
        height, width = best_indices.shape
        ii, jj = numpy.ogrid[:height, :width]
        output_pixels = stack[best_indices, ii, jj]

        # Save to workspace
        new_image = Image(output_pixels)
        workspace.image_set.add(self.output_image_name.value, new_image)

        # Store for display
        if self.show_window:
            workspace.display_data.output_pixels = output_pixels

    def display(self, workspace, figure):
        """Displays the resulting projection in a CellProfiler window."""
        pixels = workspace.display_data.output_pixels
        
        figure.set_subplots((1, 1))
        # Use sharexy=True so zooming/panning works smoothly
        figure.subplot_imshow(0, 0, pixels, title=self.output_image_name.value, colormap="gray") #viridis is the default colormap, or fire

    def upgrade_settings(self, setting_values, variable_revision_number, module_name):
        return setting_values, variable_revision_number