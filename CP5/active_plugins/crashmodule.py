import logging

from cellprofiler_core.module import ImageProcessing
from cellprofiler_core.object import Objects
from cellprofiler_core.setting.choice import Choice

LOGGER = logging.getLogger(__name__)

__doc__ = f"""\
CrashModule
===========

**CrashModule** crashes

============ ============ ===============
Supports 2D? Supports 3D? Respects masks?
============ ============ ===============
YES          YES          NO
============ ============ ===============

"""

DOCKER_IMAGE_NAME = "cellprofiler/crashdocker:0.0.1"

class CrashModule(ImageProcessing):
    category = "Image Processing"

    module_name = "CrashModule"

    variable_revision_number = 1

    def create_settings(self):
        super(CrashModule, self).create_settings()

        self.y_name.set_value("OutputImage")

        self.do_crash = Choice(
            text="Crash the run",
            choices=["Yes", "No"],
            value="Yes",
            doc="""\
Cause this module to crash or succeed
""",
        )

    def settings(self):
        return super().settings() + [
            self.do_crash,
        ]

    def visible_settings(self):
        vis_settings = super().visible_settings() + [
            self.do_crash,
        ]

        return vis_settings

    def run(self, workspace):
        print("CrashModule - I am running")
        self.function = self.do_run

        measurements = workspace.measurements
        for i in range(100):
            feature = "Blah%d" % i
            measurements.add_measurement(
                "Image", feature, i
            )

        if self.do_crash == "Yes":
            super().run(workspace)
            raise Exception("I am crashing - run")
        else:
            super().run(workspace)

    def do_run(self, x_data, *args):
        return x_data
    
    def post_run(self, workspace):
        print("CrashModule - I am running post run")
        if self.do_crash == "Yes":
            raise Exception("I am crashing - post run")
        else:
            super().post_run(workspace)

    def display(self, workspace, figure):
        super().display(workspace, figure)

    def upgrade_settings(self, setting_values, variable_revision_number, module_name):
        return setting_values, variable_revision_number


