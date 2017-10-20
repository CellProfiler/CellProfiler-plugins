import os
import subprocess
import tempfile

import h5py  # HDF5 is Ilastik's preferred file format
import logging
import skimage

import cellprofiler.image
import cellprofiler.module
import cellprofiler.setting

logger = logging.getLogger(__name__)

__doc__ = """\
Predict
=======

Use an Ilastik pixel classifier to generate a probability image. Each channel represents the probability of the
pixels in the image belong to a particular class. Use **ColorToGray** to separate channels for further processing. For
example, use **IdentifyPrimaryObjects** on a (single-channel) probability map to generate a segmentation. The order of 
the channels in **ColorToGray** is the same as the order of the labels within the Ilastik project.

It is recommended that you pre-process any training images with CellProfiler (e.g., **RescaleIntensity**) and apply the
same pre-processing steps to your analysis pipeline. You can use **SaveImages** to export training images as 32-bit
TIFFs.

Additionally, please ensure CellProfiler is configured to load images in the same format as Ilastik. For example, 
if your Ilastik classifier is trained on RGB images, use **NamesAndTypes** to load images as RGB by selecting 
"*Color image*" from the *Select the image type* dropdown. If your classifier expects grayscale images, use 
**NamesAndTypes** to load images as "*Grayscale image*".
"""


class Predict(cellprofiler.module.ImageProcessing):
    module_name = "Predict"

    variable_revision_number = 1

    def create_settings(self):
        super(Predict, self).create_settings()

        self.executable = cellprofiler.setting.Pathname(
            "Executable",
            doc="Ilastik command line executable name, or location if it is not on your path."
        )

        self.project_file = cellprofiler.setting.Pathname(
            "Project file",
            doc="Path to the project file (*.ilp)."
        )

        self.project_type = cellprofiler.setting.Choice(
            "Select method for constructing file names",
            [
                "Pixel Classification",
                "Autocontext (2-stage)"
            ],
            "Pixel Classification",
            doc="""\
CellProfiler supports two types of ilastik projects:

- Pixel Classification
- Autocontext (2-stage)
"""
        )

    def settings(self):
        settings = super(Predict, self).settings()

        settings += [
            self.executable,
            self.project_file,
            self.project_type
        ]

        return settings

    def visible_settings(self):
        visible_settings = super(Predict, self).visible_settings()

        visible_settings += [
            self.executable,
            self.project_file,
            self.project_type
        ]

        return visible_settings

    def run(self, workspace):
        image = workspace.image_set.get_image(self.x_name.value)

        x_data = image.pixel_data

        fin = tempfile.NamedTemporaryFile(suffix=".h5", delete=False)

        fout = tempfile.NamedTemporaryFile(suffix=".h5", delete=False)

        cmd = [
            self.executable.value,
            "--headless",
            "--project", self.project_file.value,
            "--output_format", "hdf5"
        ]

        if self.project_type.value in ["Pixel Classification"]:
            cmd += ["--export_source", "Probabilities"]
        elif self.project_type.value in ["Autocontext (2-stage)"]:
            x_data = skimage.img_as_ubyte(x_data)  # ilastik requires UINT8. Might be relaxed in future.

            cmd = ["--export_source", "probabilities stage 2"]

        cmd += [
            "--output_filename_format", fout.name,
            fin.name
        ]

        try:
            with h5py.File(fin.name, "w") as f:
                f.create_dataset("data", data=x_data)

            fin.close()

            fout.close()

            subprocess.check_call(cmd)

            with h5py.File(fout.name, "r") as f:
                y_data = f["exported_data"].value

            y = cellprofiler.image.Image(y_data)

            workspace.image_set.add(self.y_name.value, y)

            if self.show_window:
                workspace.display_data.x_data = x_data

                workspace.display_data.y_data = y_data

                workspace.display_data.dimensions = image.dimensions
        except subprocess.CalledProcessError as cpe:
            logger.error("Command {} exited with status {}".format(cpe.output, cpe.returncode), cpe)

            raise cpe
        except IOError as ioe:
            raise ioe
        finally:
            os.unlink(fin.name)

            os.unlink(fout.name)
