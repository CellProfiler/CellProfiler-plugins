# coding=utf-8


import numpy as np

import dognet
import torch
from torch.autograd import Variable
import skimage.draw

#################################
#
# Imports from CellProfiler
#
##################################

import cellprofiler.image
import cellprofiler.module
import cellprofiler.setting

__doc__ = """\
DoGNet
======

**DoGNet** takes input synapsin1, PSD95, vGlut, and predicts the location of synapses.

|

============ ============ ===============
Supports 2D? Supports 3D? Respects masks?
============ ============ ===============
YES          NO           YES
============ ============ ===============


What do I get as output?
^^^^^^^^^^^^^^^^^^^^^^^^

A synapse prediction map.


References
^^^^^^^^^^
Kulikov V, Guo SM, Stone M, Goodman A, Carpenter A, et al. (2019) 
DoGNet: A deep architecture for synapse detection in multiplexed fluorescence images. 
PLOS Computational Biology 15(5): e1007012. https://doi.org/10.1371/journal.pcbi.1007012
"""

class DoGNet(cellprofiler.module.Module):
    category = "Advanced"
    module_name = "DoGNet"
    variable_revision_number = 1

    def create_settings(self):
        self.synapsin_image = cellprofiler.setting.ImageNameSubscriber(
            "Select the synapsin image", cellprofiler.setting.NONE, doc="""\
Select the image of the synapsin-1 channel.""")

        self.PSD95_image = cellprofiler.setting.ImageNameSubscriber(
            "Select the PSD95 image", cellprofiler.setting.NONE, doc="""\
Select the image of the PSD95 channel.""")

        self.vGlut_image = cellprofiler.setting.ImageNameSubscriber(
            "Select the vGlut image", cellprofiler.setting.NONE, doc="""\
Select the image of the vGlut channel.""")

        self.prediction_image_name = cellprofiler.setting.ImageNameProvider(
            "Output image name",
            "SynapsePrediction",
            doc="""\
Enter the name to give the output prediction image created by this module.
""")
        self.t7_name = cellprofiler.setting.Pathname(
            "Trained network location",
            doc="Specify the location of the trained network."
        )

    def settings(self):

        settings = [
            self.synapsin_image,
            self.PSD95_image,
            self.vGlut_image,
            self.prediction_image_name,
            self.t7_name
        ]

        return settings

    def run(self, workspace):
        net = dognet.SimpleAnisotropic(3,15,5,learn_amplitude=False)
        net.to('cpu')
        net.load_state_dict(torch.load(self.t7_name.value))

        syn_normed=np.expand_dims(
            self.normalize(
                workspace.image_set.get_image(self.synapsin_image.value, must_be_grayscale=True)
            )
            ,0)
        psd_normed=np.expand_dims(
            self.normalize(
                workspace.image_set.get_image(self.PSD95_image.value, must_be_grayscale=True)
            )
            ,0)
        vglut_normed=np.expand_dims(
            self.normalize(
                workspace.image_set.get_image(self.vGlut_image.value, must_be_grayscale=True)
            )
            ,0)

        data = np.concatenate([syn_normed,psd_normed,vglut_normed])
        print(data.shape)
        y = self.inference(net,data)

        output_image = cellprofiler.image.Image(y[0,0])

        workspace.image_set.add(self.prediction_image_name.value, output_image)

        if self.show_window:
            workspace.display_data.syn_pixels = workspace.image_set.get_image(self.synapsin_image.value).pixel_data

            workspace.display_data.psd_pixels = workspace.image_set.get_image(self.PSD95_image.value).pixel_data

            workspace.display_data.vglut_pixels = workspace.image_set.get_image(self.vGlut_image.value).pixel_data

            workspace.display_data.output_pixels = y[0,0]

    def display(self, workspace, figure):
        dimensions = (2, 2)

        figure.set_subplots(dimensions)

        figure.subplot_imshow_grayscale(0, 0, workspace.display_data.syn_pixels, "Synapsin")

        figure.subplot_imshow_grayscale(
            1,
            0,
            workspace.display_data.psd_pixels,
            "PSD-95",
            sharexy=figure.subplot(0, 0),
        )

        figure.subplot_imshow_grayscale(
            0,
            1,
            workspace.display_data.vglut_pixels,
            "vGlut",
            sharexy=figure.subplot(0, 0),
        )

        figure.subplot_imshow_grayscale(
            1,
            1,
            workspace.display_data.output_pixels,
            "Synapse prediction",
            sharexy=figure.subplot(0, 0),
        )

    def normalize(self, im):
        meanx = im.pixel_data.mean()
        minx = im.pixel_data.min()
        maxx = im.pixel_data.max()
        x = np.copy(im.pixel_data.astype(np.float32))
        x = (x - meanx - minx)/(maxx - minx).astype(np.float32)
        return x

    def inference(self, net,image,get_intermediate=False):
        x = np.expand_dims(image,0)
        vx = Variable(torch.from_numpy(x).float()).to('cpu')

        res,inter = net(vx)
        if get_intermediate:
            return res.data.cpu().numpy(),inter.data.cpu().numpy()
        return res.data.cpu().numpy()

    def volumetric(self):
        return False


