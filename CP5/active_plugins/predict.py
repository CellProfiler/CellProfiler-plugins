#################################
#
# Imports from useful Python libraries
#
#################################

import os
import subprocess
import tempfile
import h5py  # HDF5 is ilastik's preferred file format
import logging
import skimage

#################################
#
# Imports from CellProfiler
#
##################################

from cellprofiler_core.image import Image
from cellprofiler_core.module import Module
import cellprofiler_core.setting
from cellprofiler_core.setting.choice import Choice
from cellprofiler_core.setting.text import Pathname

__doc__ = """\
Predict
=======

**Predict** uses an ilastik pixel classifier to generate a probability image. Each
channel represents the probability of the pixels in the image belong to
a particular class. Use **ColorToGray** to separate channels for further
processing. For example, use **IdentifyPrimaryObjects** on a
(single-channel) probability map to generate a segmentation. The order
of the channels in **ColorToGray** is the same as the order of the
labels within the ilastik project.

Additionally, please ensure CellProfiler is configured to load images in
the same format as ilastik. For example, if your ilastik classifier is
trained on RGB images, use **NamesAndTypes** to load images as RGB by
selecting "*Color image*" from the *Select the image type* dropdown. If
your classifier expects grayscale images, use **NamesAndTypes** to load
images as "*Grayscale image*".

|

============ ============ ===============
Supports 2D? Supports 3D? Respects masks?
============ ============ ===============
YES          NO           NO
============ ============ ===============
"""

logger = logging.getLogger(__name__)


class Predict(cellprofiler_core.module.ImageProcessing):
    module_name = "Predict"

    variable_revision_number = 2

    def create_settings(self):
        super(Predict, self).create_settings()

        self.executable = Pathname(
            "Executable",
            doc="ilastik command line executable name, or location if it is not on your path.",
        )

        self.project_file = Pathname(
            "Project file", doc="Path to the project file (\*.ilp)."
        )

        self.project_type = Choice(
            "Select the project type",
            ["Pixel Classification", "Autocontext (2-stage)"],
            "Pixel Classification",
            doc="""\
Select the project type which matches the project file specified by
*Project file*. CellProfiler supports two types of ilastik projects:

-  *Pixel Classification*: Classify the pixels of an image given user
   annotations. `Read more`_.

-  *Autocontext (2-stage)*: Perform pixel classification in multiple
   stages, sharing predictions between stages to improve results. `Read
   more <http://ilastik.org/documentation/autocontext/autocontext>`__.

.. _Read more: http://ilastik.org/documentation/pixelclassification/pixelclassification
""",
        )

    def settings(self):
        settings = super(Predict, self).settings()

        settings += [self.executable, self.project_file, self.project_type]

        return settings

    def visible_settings(self):
        visible_settings = super(Predict, self).visible_settings()

        visible_settings += [self.executable, self.project_file, self.project_type]

        return visible_settings

    def run(self, workspace):
        image = workspace.image_set.get_image(self.x_name.value)

        x_data = image.pixel_data
        x_data = x_data*image.scale

        fin = tempfile.NamedTemporaryFile(suffix=".h5", delete=False)

        fout = tempfile.NamedTemporaryFile(suffix=".h5", delete=False)

        if self.executable.value[-4:] == ".app":
            executable = os.path.join(self.executable.value, "Contents/MacOS/ilastik")
        else:
            executable = self.executable.value

        cmd = [
            executable,
            "--headless",
            "--project",
            self.project_file.value,
            "--output_format",
            "hdf5",
        ]

        if self.project_type.value in ["Pixel Classification"]:
            cmd += ["--export_source", "Probabilities"]
        elif self.project_type.value in ["Autocontext (2-stage)"]:

            cmd += ["--export_source", "probabilities stage 2"]
            # cmd += ["--export_source", "probabilities all stages"]

        cmd += ["--output_filename_format", fout.name, fin.name]

        try:
            with h5py.File(fin.name, "w") as f:
                shape = x_data.shape

                f.create_dataset("data", shape, data=x_data)

            fin.close()

            fout.close()

            subprocess.check_call(cmd)

            with h5py.File(fout.name, "r") as f:
                y_data = f["exported_data"][()]

            y = Image(y_data)

            workspace.image_set.add(self.y_name.value, y)

            if self.show_window:
                workspace.display_data.x_data = x_data

                workspace.display_data.y_data = y_data

                workspace.display_data.dimensions = image.dimensions
        except subprocess.CalledProcessError as cpe:
            logger.error(
                "Command {} exited with status {}".format(cpe.output, cpe.returncode),
                cpe,
            )

            raise cpe
        except IOError as ioe:
            raise ioe
        finally:
            os.unlink(fin.name)

            os.unlink(fout.name)
