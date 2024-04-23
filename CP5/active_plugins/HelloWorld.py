import matplotlib.pyplot as plt
from matplotlib import patheffects
import numpy as np

import cellprofiler_core.module
import cellprofiler_core.setting.text

__doc__ = """\
HelloWorld
============

**HelloWorld** takes an image, and overlays "Hello World!" on top of it, by default.


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

class HelloWorld(cellprofiler_core.module.ImageProcessing):
    module_name = "HelloWorld"

    variable_revision_number = 1

    def create_settings(self):
        super().create_settings()
        self.y_name.set_value("OverlayImage")
        self.overlay_text = cellprofiler_core.setting.text.Text("Overlay Text", "Hello World!", doc="The text you would like to be overlayed on top of the image.")

    def settings(self):
        return super().settings() + [self.overlay_text]
    
    # normally unnecessary, but ImageProcessing defines this so we have to too
    def visible_settings(self):
        return self.settings()

    def run(self, workspace):
        self.function = self.place_text_on_image
        super().run(workspace)

    def place_text_on_image(self,
                            img,
                            text,
                            x_pos = 0, 
                            y_pos = 0.99, 
                            color = "white", 
                            weight = "bold", 
                            ha = "left", 
                            va = "top", 
                            outline_color = "black", 
                            outline_width = 3):
        fig = plt.figure()
        fig.figimage(img, resize=True)

        fontsize = 34/400*img.shape[0]

        # Main text
        txt = fig.text(x_pos, y_pos, text, fontsize=fontsize, color=color, weight=weight, 
                    horizontalalignment=ha, verticalalignment=va)

        # Apply white outline using path_effects
        outline_effect = patheffects.withStroke(linewidth=outline_width, foreground=outline_color)
        txt.set_path_effects([outline_effect])

        fig.canvas.draw()
        annotated_img = np.asarray(fig.canvas.renderer.buffer_rgba())
        plt.close(fig)
        return annotated_img
