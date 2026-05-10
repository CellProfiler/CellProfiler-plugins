import numpy
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
            "ProjectionBlue",
            doc="Enter the name for the projected image."
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
        bright_max = None
        bright_min = None
        norm0 = None
        reference_image = None
        final_mask = None

        for i, group in enumerate(self.stack_channels):
            img_name = group.image_name.value
            if img_name == "None":
                continue
                
            image_obj = workspace.image_set.get_image(img_name)
            pixels = image_obj.pixel_data.copy()
            mask = image_obj.mask if image_obj.has_mask else numpy.ones(pixels.shape[:2], bool)

            if bright_max is None:
                # Initialization (replicates set_image)
                reference_image = image_obj
                bright_max = pixels.copy()
                bright_min = pixels.copy()
                norm0 = numpy.mean(pixels)
                final_mask = mask.copy()
            else:
                # Accumulation (replicates accumulate_image for P_BRIGHTFIELD)
                norm = numpy.mean(pixels)
                # Normalize pixels relative to the first image
                rescaled_pixels = pixels * (norm0 / norm) if norm != 0 else pixels
                
                # Identify where new pixels are higher/lower
                max_mask = (bright_max < rescaled_pixels) & mask
                min_mask = (bright_min > rescaled_pixels) & mask
                
                bright_min[min_mask] = rescaled_pixels[min_mask]
                bright_max[max_mask] = rescaled_pixels[max_mask]
                
                # This specific line from your source ensures min follows max if max is updated
                bright_min[max_mask] = bright_max[max_mask]
                
                # Combine masks (replicates P_MASK or standard mask handling)
                final_mask = final_mask & mask

        if bright_max is not None:
            # Replicates provide_image: result = max - min
            output_pixels = bright_max - bright_min
            
            # CRITICAL: Setting parent_image ensures SaveImages/FlagImages works
            new_image = Image(output_pixels, mask=final_mask, parent_image=reference_image)
            workspace.image_set.add(self.output_image_name.value, new_image)

            if self.show_window:
                workspace.display_data.output_pixels = output_pixels

    def display(self, workspace, figure):
        if hasattr(workspace.display_data, 'output_pixels'):
            pixels = workspace.display_data.output_pixels
            figure.set_subplots((1, 1))
            figure.subplot_imshow(0, 0, pixels, title=self.output_image_name.value, colormap="gray")

    def upgrade_settings(self, setting_values, variable_revision_number, module_name):
        return setting_values, variable_revision_number