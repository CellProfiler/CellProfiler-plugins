import cellprofiler_core.module
from cellprofiler_core.setting.subscriber import ImageSubscriber
from cellprofiler_core.setting.text import ImageName
from cellprofiler_core.setting.text import Text
from cellprofiler_core.setting import Binary
from cellprofiler_core.setting import Color

__doc__ = """\
DumpIt
======

**DumpIt** does nothing of interest yet.


I am a module
look at me,
about as simple
as could be.

|

============ ============ ===============
Supports 2D? Supports 3D? Respects masks?
============ ============ ===============
YES          NO            YES
============ ============ ===============

"""

class DumpIt(cellprofiler_core.module.ImageProcessing):
    module_name = "DumpIt"

    variable_revision_number = 1

    def create_settings(self):
        self.x_name = ImageSubscriber(
            "Select the input image", doc="Select the image you want to use."
        )

        self.y_name = ImageName(
            "Name the output image",
            self.__class__.__name__,
            doc="Enter the name you want to call the image produced by this module.",
        )
        self.overlay_text = Text("Some Text", "Hello World!", doc="The text you would like to be overlayed on top of the image.")
        
        self.binary = Binary("Some binary", True)
        self.color = Color("Some color choice", "red")

    def settings(self):
        return [self.x_name, self.y_name, self.overlay_text, self.binary,
                self.color]
    
    def visible_settings(self):
        return self.settings()

    def run(self, workspace):
        self.function = lambda x_data, args: ...
        super().run(workspace)
