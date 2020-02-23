# coding=utf-8


import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import Rectangle,Ellipse

import dognet
import torch
from torch.autograd import Variable
import pandas as pd
from sklearn.metrics import roc_curve, auc
import skimage.draw
from skimage.io import imread

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

class DoGNet(cellprofiler.module.ImageProcessing):

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
            self.synapsin_image
            self.PSD95_image,
            self.vGlut_image,
            self.prediction_image_name,
            self.t7_name
        ]

        return settings

    def run(self, workspace):

        meanx = pic.mean(axis=(1,2))
        minx = pic.min(axis=(1,2))
        maxx = pic.max(axis=(1,2))
        
        net = dognet.SimpleAnisotropic(3,11,2,learn_amplitude=False)
        net.to('cpu')
        net.load_state_dict(torch.load(self.t7_name))

        norm_raw = self.normalize(raw,self.get_normparams(raw))

        data = np.concatenate([np.expand_dims(norm_raw[channels.index(s)],0) for s in req_channels])
        y = self.inference(net,data)
        xx,yy,_ = dognet.find_peaks(y[0,0],3)
        pic= (data-data.min())/(data.max()-data.min())

    def get_normparams(self, data):
        return data.mean(axis=(1,2)),data.min(axis=(1,2)),data.max(axis=(1,2))

    def normalize(self, im,norm_data):
        meanx,minx,maxx = norm_data
        x = np.copy(im.astype(np.float32))
        x = x.transpose(1,2,0)
        x = (x - meanx - minx)/(maxx - minx).astype(np.float32)
        return x.transpose(2,0,1)

    def inference(self, net,image,get_intermediate=False):
        x = np.expand_dims(image,0)
        vx = Variable(torch.from_numpy(x).float()).to('cpu')

        res,inter = net(vx)
        if get_intermediate:
            return res.data.cpu().numpy(),inter.data.cpu().numpy()
        return res.data.cpu().numpy()

    def make_labels(self, img,xs,ys,radius=5):
        labels = np.zeros(img.shape[1:])
        for xv,yv in zip(xs,ys):
            rr,cc = skimage.draw.circle(xv,yv,radius,labels.shape)
            rr,cc = skimage.draw.circle

            labels[rr,cc]=1
        return labels

    def volumetric(self):
        return False


