import os
import subprocess
import tempfile

import h5py  # HDF5 is Ilastik's preferred file format
import logging

import cellprofiler.image
import cellprofiler.module
import cellprofiler.setting

logger = logging.getLogger(__name__)

__doc__ = """
Use an Ilastik pixel classifier to generate a probability image. Each channel of represents the probability of the
pixels in the image belong to a particular class. Use ColorToGray to separate channels for further processing. For
example, use IdentifyPrimaryObjects on a (single-channel) probability map to generate a segmentation.

It is recommended that you pre-process any training images with CellProfiler (e.g., RescaleIntensity) and apply the
same pre-processing steps to your analysis pipeline. You should use SaveImages to export training images as 64-bit
TIFFs.
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

    def settings(self):
        settings = super(Predict, self).settings()

        settings += [
            self.executable,
            self.project_file
        ]

        return settings

    def visible_settings(self):
        visible_settings = super(Predict, self).visible_settings()

        visible_settings += [
            self.executable,
            self.project_file
        ]

        return visible_settings

    def run(self, workspace):
        image = workspace.image_set.get_image(self.x_name.value)

        x_data = image.pixel_data

        fin = tempfile.NamedTemporaryFile(suffix=".h5", delete=False)

        fout = tempfile.NamedTemporaryFile(suffix=".h5", delete=False)

        try:
            with h5py.File(fin.name, "w") as f:
                f.create_dataset("data", data=x_data)

            fin.close()

            fout.close()

            cmd = [
                self.executable.value,
                "--headless",
                "--project", self.project_file.value,
                "--output_format", "hdf5",
                "--export_source", "Probabilities",
                "--output_filename_format", fout.name,
                fin.name
            ]

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
