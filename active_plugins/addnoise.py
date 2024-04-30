"""
AddNoise
========================

**AddNoise** adds noise to an image.

|

============ ============ ===============
Supports 2D? Supports 3D? Respects masks?
============ ============ ===============
YES          YES           NO
============ ============ ===============

"""

import numpy
from cellprofiler_core.image import Image
from cellprofiler_core.module import Module
from cellprofiler_core.setting import Divider, Binary
from cellprofiler_core.setting import SettingsGroup
from cellprofiler_core.setting.choice import Choice
from cellprofiler_core.setting.do_something import DoSomething
from cellprofiler_core.setting.do_something import RemoveSettingButton
from cellprofiler_core.setting.subscriber import ImageSubscriber
from cellprofiler_core.setting.text import ImageName
from cellprofiler_core.setting.text import Float

SETTINGS_PER_IMAGE = 2

A_GAUSSIAN = "Gaussian"
A_POISSON = "Poisson"
A_SANDP = "Salt and Pepper"

G_MU = "mu"
G_SIGMA = "sigma"

I_PERCENT = "Percent image with noise"

class AddNoise(Module):
    category = "Image Processing"
    variable_revision_number = 1
    module_name = "AddNoise"

    def create_settings(self):
        """Make settings here (and set the module name)"""
        self.images = []
        self.add_image(can_delete=False)
        self.add_image_button = DoSomething("", "Add another image", self.add_image)
        self.truncate_low = Binary(
            "Set output image values less than 0 equal to 0?", 
            True, 
            doc="""\
Values outside the range 0 to 1 might not be handled well by other
modules. Select *"Yes"* to set negative values to 0, which was previously
done automatically without ability to override.
""" )

        self.truncate_high = Binary(
            "Set output image values greater than 1 equal to 1?", 
            True, 
            doc="""\
Values outside the range 0 to 1 might not be handled well by other
modules. Select *"Yes"* to set values greater than 1 to a maximum
value of 1.
""")
        self.method = Choice(
            "Select the operation",
            [A_GAUSSIAN, A_POISSON, A_SANDP],
            doc="""\
Select what kind of noise you want to add.

-  *{A_GAUSSIAN}:* Gaussian noise has a normally distributed probability density function. 
It is independent of the original intensities in the image.
{G_MU} is the mean and {G_SIGMA} is the standard deviation.
-  *{A_POISSON}:* Poisson noise is correlated with the intensity of each pixel. Also called Shot Noise.
-  *{A_SANDP}:* Salt and Pepper is a type of impulse noise where there is a sparse occurance of maximum and minimum pixel values in an image.
You can set the {I_PERCENT}.
""".format(
                **{"A_GAUSSIAN": A_GAUSSIAN, "A_POISSON": A_POISSON, "A_SANDP": A_SANDP,
                   "G_MU": G_MU, "G_SIGMA": G_SIGMA, "I_PERCENT": I_PERCENT},
            ),
        )

        self.mu = Float(
            "mu (mean)",
            value = 0,
            doc="""\
*(Used only if “{A_GAUSSIAN}” is selected)*
Enter the mean of the Gaussian noise
""".format(
                **{
                    "A_GAUSSIAN": A_GAUSSIAN
                }
            ),
        )

        self.sigma = Float(
            "sigma (standard deviation)",
            value = .1,
            doc="""\
*(Used only if “{A_GAUSSIAN}” is selected)*
Enter the standard deviation of the Gaussian noise
""".format(
                **{
                    "A_GAUSSIAN": A_GAUSSIAN
                }
            ),
        )

        self.percent = Float(
            "percent of image to salt and pepper",
            value = .1,
            doc="""\
*(Used only if “{A_SANDP}” is selected)*
Enter the percentage of the image to salt and pepper
""".format(
                **{
                    "A_SANDP": A_SANDP
                }
            ),
        )


    def add_image(self, can_delete=True):
        """Add an image and its settings to the list of images"""
        image_name = ImageSubscriber(
            "Select the input image", "None", doc="Select the image to add noise to."
        )

        noised_image_name = ImageName(
            "Name the output image",
            "NoisedBlue",
            doc="Enter a name for the noisy image.",
        )

        image_settings = SettingsGroup()
        image_settings.append("image_name", image_name)
        image_settings.append("noised_image_name", noised_image_name)

        if can_delete:
            image_settings.append(
                "remover",
                RemoveSettingButton(
                    "", "Remove this image", self.images, image_settings
                ),
            )
        image_settings.append("divider", Divider())
        self.images.append(image_settings)

    def settings(self):
        """Return the settings to be loaded or saved to/from the pipeline

        These are the settings (from cellprofiler_core.settings) that are
        either read from the strings in the pipeline or written out
        to the pipeline. The settings should appear in a consistent
        order so they can be matched to the strings in the pipeline.
        """
        result = [self.method,self.mu,self.sigma]
        for image in self.images:
            result += [
                image.image_name,
                image.noised_image_name,
            ]
        result += [
            self.truncate_low,
            self.truncate_high,
        ]
        return result

    def visible_settings(self):
        """Return the list of displayed settings
        """
        result = [self.method]
        for image in self.images:
            result += [
                image.image_name,
                image.noised_image_name,
            ]
            #
            # Get the "remover" button if there is one
            #
            remover = getattr(image, "remover", None)
            if remover is not None:
                result.append(remover)
            result.append(image.divider)
        result.append(self.add_image_button)
        result.append(self.truncate_low)
        result.append(self.truncate_high)
        if self.method == A_GAUSSIAN:
            result.append(self.mu)
            result.append(self.sigma)
        if self.method == A_SANDP:
            result.append(self.percent)
        return result

    def run(self, workspace):
        """Run the module

        workspace    - The workspace contains
            pipeline     - instance of cpp for this run
            image_set    - the images in the image set being processed
            object_set   - the objects (labeled masks) in this image set
            measurements - the measurements for this run
            frame        - the parent frame to whatever frame is created. None means don't draw.
        """
        for image in self.images:
            self.run_image(image, workspace)

    def run_image(self, image, workspace):
        #
        # Get the image names from the settings
        #
        image_name = image.image_name.value
        noised_image_name = image.noised_image_name.value
        #
        # Get images from the image set
        #
        orig_image = workspace.image_set.get_image(image_name, must_be_grayscale=True)

        if self.method.value == A_GAUSSIAN:
            output_pixels = self.add_gaussian(orig_image, self.mu.value, self.sigma.value)
        if self.method.value == A_POISSON:
            output_pixels = self.add_poisson(orig_image)
        if self.method.value == A_SANDP:
            output_pixels = self.add_impulse(orig_image, self.percent.value)
        #
        # Optionally, clip high and low values
        #
        if self.truncate_low.value:
            output_pixels = numpy.where(output_pixels < 0, 0, output_pixels)
        if self.truncate_high.value:
            output_pixels = numpy.where(output_pixels > 1, 1, output_pixels)
        
        y = Image(dimensions=orig_image.dimensions, image=output_pixels, parent_image=orig_image, convert=False)
        workspace.image_set.add(noised_image_name, y)
        #
        # Save images for display
        #
        if self.show_window:
            if not hasattr(workspace.display_data, "images"):
                workspace.display_data.images = {}
            workspace.display_data.images[image_name] = orig_image.pixel_data
            workspace.display_data.images[noised_image_name] = output_pixels
    
    def add_gaussian(self, orig_image, mu, sigma):
        noise_mask = numpy.random.normal(mu, sigma, orig_image.pixel_data.shape)
        noisy_pixels = orig_image.pixel_data + noise_mask
        return noisy_pixels
    def add_poisson(self, orig_image):
        noise_mask = numpy.random.poisson(orig_image.pixel_data)
        noisy_pixels = orig_image.pixel_data + noise_mask
        return noisy_pixels      
    def add_impulse(self, orig_image, percent):
        random_indices = numpy.random.choice(orig_image.pixel_data.size, round(orig_image.pixel_data.size*percent))
        noise = numpy.random.choice([orig_image.pixel_data.min(), orig_image.pixel_data.max()], round(orig_image.pixel_data.size*percent))
        noisy_pixels = orig_image.pixel_data.copy()
        noisy_pixels.flat[random_indices] = noise
        return noisy_pixels
    
    def display(self, workspace, figure):
        """ Display one row of orig / noised per image setting group"""
        figure.set_subplots((2, len(self.images)))
        for j, image in enumerate(self.images):
            image_name = image.image_name.value
            noised_image_name = image.noised_image_name.value
            orig_image = workspace.display_data.images[image_name]
            noised_image = workspace.display_data.images[noised_image_name]

            def imshow(x, y, image, *args, **kwargs):
                if image.ndim == 2:
                    f = figure.subplot_imshow_grayscale
                else:
                    f = figure.subplot_imshow_color
                return f(x, y, image, *args, **kwargs)

            imshow(
                0,
                j,
                orig_image,
                "Original image: %s" % image_name,
                sharexy=figure.subplot(0, 0),
            )
            imshow(
                1,
                j,
                noised_image,
                "Final image: %s" % noised_image_name,
                sharexy=figure.subplot(0, 0),
            )

