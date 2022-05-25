"""
<b>Enhanced Measure Texture</b> measures the degree and nature of textures within objects (versus smoothness)
<hr>

This module measures the variations in grayscale images.  An object (or 
entire image) without much texture has a smooth appearance; an
object or image with a lot of texture will appear rough and show a wide 
variety of pixel intensities.

<p>This module can also measure textures of objects against grayscale images. 
Any input objects specified will have their texture measured against <i>all</i> input
images specfied, which may lead to image-object texture combinations that are unneccesary. 
If you do not want this behavior, use multiple <b>EnhancedMeasureTexture</b> modules to 
specify the particular image-object measures that you want.</p>
                        

<h4>Available measurements</h4>
<ul>
<li><i>Haralick Features:</i> Haralick texture features are derived from the 
co-occurrence matrix, which contains information about how image intensities in pixels with a 
certain position in relation to each other occur together. <b>EnhancedMeasureTexture</b>
can measure textures at different scales; the scale you choose determines
how the co-occurrence matrix is constructed.
For example, if you choose a scale of 2, each pixel in the image (excluding
some border pixels) will be compared against the one that is two pixels to
the right. <b>EnhancedMeasureTexture</b> quantizes the image into eight intensity
levels. There are then 8x8 possible ways to categorize a pixel with its
scale-neighbor. <b>EnhancedMeasureTexture</b> forms the 8x8 co-occurrence matrix
by counting how many pixels and neighbors have each of the 8x8 intensity
combinations. Thirteen features are then calculated for the image by performing
mathematical operations on the co-occurrence matrix (the forumulas can be found 
<a href="http://murphylab.web.cmu.edu/publications/boland/boland_node26.html">here</a>):
<ul>
<li><i>H1:</i> Angular Second Moment</li>
<li><i>H2:</i> Contrast</li>
<li><i>H3:</i> Correlation</li>
<li><i>H4:</i> Sum of Squares: Variation</li>
<li><i>H5:</i> Inverse Difference Moment</li>
<li><i>H6:</i> Sum Average</li>
<li><i>H7:</i> Sum Variance</li>
<li><i>H8:</i> Sum Entropy</li>
<li><i>H9:</i> Entropy</li>
<li><i>H10:</i> Difference Variance</li>
<li><i>H11:</i> Difference Entropy</li>
<li><i>H12:</i> Information Measure of Correlation 1</li>
<li><i>H13:</i> Information Measure of Correlation 2</li>
</ul>
</li>
<li>
<i>Gabor "wavelet" features:</i> These features are similar to wavelet features, 
and they are obtained by applying so-called Gabor filters to the image. The Gabor 
filters measure the frequency content in different orientations. They are very 
similar to wavelets, and in the current context they work exactly as wavelets, but
they are not wavelets by a strict mathematical definition. The Gabor
features detect correlated bands of intensities, for instance, images of
Venetian blinds would have high scores in the horizontal orientation.</li>
</ul>

<h3>Technical notes</h3> 
<p><b>EnhancedMeasureTexture</b> performs the following algorithm to compute a score
at each scale using the Gabor filter:
<ul>
<li>Divide the half-circle from 0 to 180&deg; by the number of desired
angles. For instance, if the user chooses two angles, EnhancedMeasureTexture
uses 0 and 90 &deg; (horizontal and vertical) for the filter
orientations. This is the Theta value from the reference paper.</li>
<li>For each angle, compute the Gabor filter for each object in the image
at two phases separated by 90&deg; in order to account for texture
features whose peaks fall on even or odd quarter-wavelengths.</li>
<li>Multiply the image times each Gabor filter and sum over the pixels
in each object.</li>
<li>Take the square root of the sum of the squares of the two filter scores.
This results in one score per Theta.</li>
<li>Save the maximum score over all Theta as the score at the desired scale.</li>
</ul>
</p>
<h3>Changes from CellProfiler 1.0</h3>
CellProfiler 2.0 normalizes the co-occurence matrix of the Haralick features
per object by basing the intensity levels of the matrix on the maximum and
minimum intensity observed within each object. CellProfiler 1.0 normalizes
the co-occurrence matrix based on the maximum and minimum intensity observed
among all objects in each image. CellProfiler 2.0's measurements should be
more informative especially for objects whose maximum intensities vary
substantially because each object will have the full complement of levels;
in CellProfiler 1.0, only the brightest object would have the full dynamic
range. Measurements of Haralick features may differ substantially between
CellProfiler 1.0 and 2.0.

CellProfiler 1.0 constructs a single kernel for the Gabor filter operation, with
a fixed size of slightly less than the median radius of the objects in an image and 
a single exponential fall-off based on this median radius. The texture of pixels not 
covered by the kernel is not measured. In contrast, CellProfiler 2.0 performs a 
vectorized calculation of the Gabor filter, properly scaled to the size of the 
object being measured and covering all pixels in the object. CellProfiler 2.0's 
Gabor filter can be calculated at a user-selected number of angles whereas 
CellProfiler 1.0's Gabor filter is calculated only at angles of 0&deg; and 90&deg;.

References
<ul>
<li>Haralick et al. (1973), "Textural Features for Image
Classification," <i>IEEE Transaction on Systems Man, Cybernetics</i>,
SMC-3(6):610-621.</li>
<li>Gabor D. (1946). "Theory of communication," 
<i>Journal of the Institute of Electrical Engineers</i> 93:429-441.</li>
</ul>
"""

# CellProfiler is distributed under the GNU General Public License.
# See the accompanying file LICENSE for details.
# 
# Copyright (c) 2003-2009 Massachusetts Institute of Technology
# Copyright (c) 2009-2012 Broad Institute
# 
# Please see the AUTHORS file for credits.
# 
# Website: http://www.cellprofiler.org


__version__ = "$Revision$"

import numpy as np
import scipy.ndimage as scind

import calculatemoments as cpmoments
import cellprofiler_core.module as cpm
import cellprofiler_core.object as cpo
import cellprofiler_core.setting as cps
import cellprofiler_core.measurement as cpmeas
from cellprofiler_core.constants.measurement import COLTYPE_FLOAT
from cellprofiler_core.setting.do_something import DoSomething
from cellprofiler_core.setting.multichoice import MultiChoice
from cellprofiler_core.setting.subscriber import ImageSubscriber, LabelSubscriber
from cellprofiler_core.setting.text import Integer
from cellprofiler_core.utilities.core.object import size_similarly
from centrosome.cpmorphology import fixup_scipy_ndimage_result as fix
from centrosome.haralick import Haralick, normalized_per_object
from centrosome.filter import gabor, stretch

"""The category of the per-object measurements made by this module"""
TEXTURE = 'Texture'

"""The "name" slot in the object group dictionary entry"""
OG_NAME = 'name'
"""The "remove"slot in the object group dictionary entry"""
OG_REMOVE = 'remove'

F_HARALICK = """AngularSecondMoment Contrast Correlation Variance 
InverseDifferenceMoment SumAverage SumVariance SumEntropy Entropy
DifferenceVariance DifferenceEntropy InfoMeas1 InfoMeas2""".split()

F_GABOR = "Gabor"

H_HORIZONTAL = "Horizontal"
A_HORIZONTAL = "0"
H_VERTICAL = "Vertical"
A_VERTICAL = "90"
H_DIAGONAL = "Diagonal"
A_DIAGONAL = "45"
H_ANTIDIAGONAL = "Anti-diagonal"
A_ANTIDIAGONAL = "135"
H_ALL = [H_HORIZONTAL, H_VERTICAL, H_DIAGONAL, H_ANTIDIAGONAL]

H_TO_A = { H_HORIZONTAL: A_HORIZONTAL,
           H_VERTICAL: A_VERTICAL,
           H_DIAGONAL: A_DIAGONAL,
           H_ANTIDIAGONAL: A_ANTIDIAGONAL }

F_TAMURA="Tamura"
F_1="Coarseness"
F_2="Contrast"
F_3="Directionality"
F_ALL=[F_1, F_2, F_3]

HIST_COARS_BINS=3
NB_SCALES=5
DIR_BINS=125

class EnhancedMeasureTexture(cpm.Module):

    module_name = "EnhancedMeasureTexture"
    variable_revision_number = 3
    category = 'Measurement'

    def create_settings(self):
        """Create the settings for the module at startup.
        
        The module allows for an unlimited number of measured objects, each
        of which has an entry in self.object_groups.
        """ 
        self.image_groups = []
        self.object_groups = []
        self.scale_groups = []
        self.image_count = cps.HiddenCount(self.image_groups)
        self.object_count = cps.HiddenCount(self.object_groups)
        self.scale_count = cps.HiddenCount(self.scale_groups)
        self.add_image_cb(can_remove = False)
        self.add_images = DoSomething("", "Add another image",
                                          self.add_image_cb)
        self.image_divider = cps.Divider()
        self.add_object_cb(can_remove = True)
        self.add_objects = DoSomething("", "Add another object",
                                           self.add_object_cb)
        self.object_divider = cps.Divider()
        self.add_scale_cb(can_remove = False)
        self.add_scales = DoSomething("", "Add another scale",
                                          self.add_scale_cb)
        self.scale_divider = cps.Divider()
        
        self.wants_gabor = cps.Binary(
            "Measure Gabor features?", True, doc =
            """The Gabor features measure striped texture in an object. They
            take a substantial time to calculate. Check this setting to
            measure the Gabor features. Uncheck this setting to skip
            the Gabor feature calculation if it is not informative for your
            images""")
        self.gabor_angles = Integer("Number of angles to compute for Gabor",4,2, doc="""
        <i>(Used only if Gabor features are measured)</i><br>
        How many angles do you want to use for each Gabor texture measurement?
            The default value is 4 which detects bands in the horizontal, vertical and diagonal
            orientations.""")
        self.gabor_divider = cps.Divider()
        
        self.wants_tamura = cps.Binary(
            "Measure Tamura features?", True, doc =
            """The Tamura features are very ugly.""")
        self.tamura_feats=MultiChoice(
                    "Features to compute", F_ALL, F_ALL,
                    doc = """Tamura Features:
                        <p><ul>
                        <li><i>%(F_1)s</i> - bla.</li>
                        <li><i>%(F_2)s</i> - bla.</li>
                        <li><i>%(F_3)s</i> - bla.</li>
                        </ul><p>
                        Choose one or more features to compute.""" % globals())           

    def settings(self):
        """The settings as they appear in the save file."""
        result = [self.image_count, self.object_count, self.scale_count]
        for groups, elements in [(self.image_groups, ['image_name']),
                                (self.object_groups, ['object_name']),
                                (self.scale_groups, ['scale', 'angles'])]:
            for group in groups:
                for element in elements:
                    result += [getattr(group, element)]
        result += [self.wants_gabor, self.gabor_angles]
        result += [self.wants_tamura, self.tamura_feats]
        return result

    def prepare_settings(self,setting_values):
        """Adjust the number of object groups based on the number of
        setting_values"""
        for count, sequence, fn in\
            ((int(setting_values[0]), self.image_groups, self.add_image_cb),
             (int(setting_values[1]), self.object_groups, self.add_object_cb),
             (int(setting_values[2]), self.scale_groups, self.add_scale_cb)):
            del sequence[count:]
            while len(sequence) < count:
                fn()
        
    def visible_settings(self):
        """The settings as they appear in the module viewer"""
        result = []
        for groups, add_button, div in [(self.image_groups, self.add_images, self.image_divider),
                                        (self.object_groups, self.add_objects, self.object_divider),
                                        (self.scale_groups, self.add_scales, self.scale_divider)]:
            for group in groups:
                result += group.visible_settings()
            result += [add_button, div]
        
        result += [self.wants_gabor]
        if self.wants_gabor:
            result += [self.gabor_angles]
        result+=[self.gabor_divider]
        
        result += [self.wants_tamura]        
        if self.wants_tamura:
            result += [self.tamura_feats]
        return result

    def add_image_cb(self, can_remove = True):
        '''Add an image to the image_groups collection
        
        can_delete - set this to False to keep from showing the "remove"
                     button for images that must be present.
        '''
        group = cps.SettingsGroup()
        if can_remove:
            group.append("divider", cps.Divider(line=False))
        group.append('image_name', 
                     ImageSubscriber("Select an image to measure","None",
                                             doc="""
                                             What did you call the grayscale images whose texture you want to measure?"""))
        if can_remove:
            group.append("remover", cps.do_something.RemoveSettingButton("", "Remove this image", self.image_groups, group))
        self.image_groups.append(group)

    def add_object_cb(self, can_remove = True):
        '''Add an object to the object_groups collection
        
        can_delete - set this to False to keep from showing the "remove"
                     button for objects that must be present.
        '''
        group = cps.SettingsGroup()
        if can_remove:
            group.append("divider", cps.Divider(line=False))
        group.append('object_name', 
                     LabelSubscriber("Select objects to measure","None", doc="""
                        What did you call the objects whose texture you want to measure? 
                        If you only want to measure the texture 
                        for the image overall, you can remove all objects using the "Remove this object" button. 
                        <p>Objects specified here will have their
                        texture measured against <i>all</i> images specfied above, which
                        may lead to image-object combinations that are unneccesary. If you
                        do not want this behavior, use multiple <b>EnhancedMeasureTexture</b>
                        modules to specify the particular image-object measures that you want.</p>"""))
        if can_remove:
            group.append("remover", cps.do_something.RemoveSettingButton("", "Remove this object", self.object_groups, group))
        self.object_groups.append(group)

    def add_scale_cb(self, can_remove = True):
        '''Add a scale to the scale_groups collection
        
        can_delete - set this to False to keep from showing the "remove"
                     button for scales that must be present.
        '''
        group = cps.SettingsGroup()
        if can_remove:
            group.append("divider", cps.Divider(line=False))
        group.append('scale', 
                     Integer("Texture scale to measure",
                                 len(self.scale_groups)+3,
                                 doc="""You can specify the scale of texture to be measured, in pixel units; 
                                 the texture scale is the distance between correlated intensities in the image. A 
                                 higher number for the scale of texture measures larger patterns of 
                                 texture whereas smaller numbers measure more localized patterns of 
                                 texture. It is best to measure texture on a scale smaller than your 
                                 objects' sizes, so be sure that the value entered for scale of texture is 
                                 smaller than most of your objects. For very small objects (smaller than 
                                 the scale of texture you are measuring), the texture cannot be measured 
                                 and will result in a undefined value in the output file."""))
        group.append('angles', MultiChoice(
            "Angles to measure", H_ALL, H_ALL,
        doc = """The Haralick texture measurements are based on the correlation
        between pixels offset by the scale in one of four directions:
        <p><ul>
        <li><i>%(H_HORIZONTAL)s</i> - the correlated pixel is "scale" pixels
        to the right of the pixel of interest.</li>
        <li><i>%(H_VERTICAL)s</i> - the correlated pixel is "scale" pixels
        below the pixel of interest.</li>
        <li><i>%(H_DIAGONAL)s</i> - the correlated pixel is "scale" pixels
        to the right and "scale" pixels below the pixel of interest.</li>
        <li><i>%(H_ANTIDIAGONAL)s</i> - the correlated pixel is "scale"
        pixels to the left and "scale" pixels below the pixel of interest.</li>
        </ul><p>
        Choose one or more directions to measure.""" % globals()))
                                
        if can_remove:
            group.append("remover", cps.do_something.RemoveSettingButton("", "Remove this scale", self.scale_groups, group))
        self.scale_groups.append(group)
        
    def validate_module(self, pipeline):
        """Make sure chosen objects, images and scales are selected only once"""
        images = set()
        for group in self.image_groups:
            if group.image_name.value in images:
                raise cps.ValidationError(
                    "%s has already been selected" %group.image_name.value,
                    group.image_name)
            images.add(group.image_name.value)
            
        objects = set()
        for group in self.object_groups:
            if group.object_name.value in objects:
                raise cps.ValidationError(
                    "%s has already been selected" %group.object_name.value,
                    group.object_name)
            objects.add(group.object_name.value)
            
        scales = set()
        for group in self.scale_groups:
            if group.scale.value in scales:
                raise cps.ValidationError(
                    "%s has already been selected" %group.scale.value,
                    group.scale)
            scales.add(group.scale.value)
            
    def get_categories(self,pipeline, object_name):
        """Get the measurement categories supplied for the given object name.
        
        pipeline - pipeline being run
        object_name - name of labels in question (or 'Images')
        returns a list of category names
        """
        if any([object_name == og.object_name for og in self.object_groups]):
            return [TEXTURE]
        elif object_name == "Image":
            return [TEXTURE]
        else:
            return []

    def get_features(self):
        '''Return the feature names for this pipeline's configuration'''
        return F_HARALICK+([F_GABOR] if self.wants_gabor else [])+([F_TAMURA] if self.wants_tamura else [])
    
    def get_measurements(self, pipeline, object_name, category):
        '''Get the measurements made on the given object in the given category
        
        pipeline - pipeline being run
        object_name - name of objects being measured
        category - measurement category
        '''
        if category in self.get_categories(pipeline, object_name):
            return self.get_features()
        return []

    def get_measurement_images(self, pipeline, object_name, category, measurement):
        '''Get the list of images measured
        
        pipeline - pipeline being run
        object_name - name of objects being measured
        category - measurement category
        measurement - measurement made on images
        '''
        measurements = self.get_measurements(pipeline, object_name, category)
        if measurement in measurements:
            return [x.image_name.value for x in self.image_groups]
        return []

    def get_measurement_scales(self, pipeline, object_name, category, 
                               measurement, image_name):
        '''Get the list of scales at which the measurement was taken

        pipeline - pipeline being run
        object_name - name of objects being measured
        category - measurement category
        measurement - name of measurement made
        image_name - name of image that was measured
        '''
        if len(self.get_measurement_images(pipeline, object_name, category,
                                           measurement)) > 0:
            if measurement == F_GABOR:
                return [x.scale.value for x in self.scale_groups]  
            if measurement == F_TAMURA:
                return []
            return sum([["%d_%s" % (x.scale.value, H_TO_A[h])
                         for h in x.angles.get_selections()]
                        for x in self.scale_groups], [])
        return []
    
    def get_measurement_columns(self, pipeline):
        '''Get column names output for each measurement.'''
        cols = []
        for feature in self.get_features():
            for im in self.image_groups:
                if feature == F_TAMURA:
                    for f in F_ALL:
                        cols += [("Image",
                                  '%s_%s_%s_%s' % (TEXTURE, feature,f, 
                                                   im.image_name.value),
                                  COLTYPE_FLOAT)]
                    for b in range(0,HIST_COARS_BINS):
                        cols += [("Image",
                                  '%s_%s_CoarsenessHist_%dBinsHist_Bin%d_%s' % (TEXTURE, feature, 
                                                                                HIST_COARS_BINS,b,
                                                                                im.image_name.value),
                                  COLTYPE_FLOAT)]
                else:
                    for sg in self.scale_groups:
                        if feature == F_GABOR:
                            cols += [("Image",
                                      '%s_%s_%s_%d' % (TEXTURE, feature, 
                                                       im.image_name.value, 
                                                       sg.scale.value),
                                      COLTYPE_FLOAT)]
                        else:
                            for angle in sg.angles.get_selections():
                                cols += [("Image",
                                          '%s_%s_%s_%d_%s' % (
                                              TEXTURE, feature, im.image_name.value, 
                                              sg.scale.value, H_TO_A[angle]),
                                          COLTYPE_FLOAT)]
                            
        for ob in self.object_groups:
            for feature in self.get_features():
                for im in self.image_groups:
                    if feature == F_TAMURA:
                        for f in F_ALL:                    
                            cols += [(ob.object_name.value,
                                      "%s_%s_%s_%s" % (
                                          TEXTURE, feature, f, im.image_name.value),
                                      COLTYPE_FLOAT)]
                        for b in range(0,HIST_COARS_BINS):
                            cols += [("Image",
                                      '%s_%s_CoarsenessHist_%dBinsHist_Bin%d_%s' % (TEXTURE, feature,
                                                                                    HIST_COARS_BINS,b, 
                                                                                    im.image_name.value),
                                      COLTYPE_FLOAT)]
                    else:
                        for sg in self.scale_groups:
                            if feature == F_GABOR:
                                cols += [(ob.object_name.value,
                                          "%s_%s_%s_%d" % (
                                              TEXTURE, feature, im.image_name.value, 
                                              sg.scale.value),
                                          COLTYPE_FLOAT)]
                            else:
                                for angle in sg.angles.get_selections():
                                    cols += [(ob.object_name.value,
                                              "%s_%s_%s_%d_%s" % (
                                                  TEXTURE, feature, 
                                                  im.image_name.value, 
                                                  sg.scale.value, H_TO_A[angle]),
                                              COLTYPE_FLOAT)]
                               
        return cols

    def is_interactive(self):
        return False
    
    def run(self, workspace):
        """Run, computing the area measurements for the objects"""
        
        statistics = [["Image","Object","Measurement","Scale","Value"]]
        for image_group in self.image_groups:
            image_name = image_group.image_name.value
            
            if self.wants_tamura:
                statistics += self.run_image_tamura(image_name, workspace)
                for object_group in self.object_groups:
                    object_name = object_group.object_name.value
                    statistics += self.run_one_tamura(image_name, 
                                                     object_name,
                                                     workspace)                    
            
            for scale_group in self.scale_groups:
                scale = scale_group.scale.value
                if self.wants_gabor:
                    statistics += self.run_image_gabor(image_name, scale, workspace)
                for angle in scale_group.angles.get_selections():
                    statistics += self.run_image(image_name, scale, angle, 
                                                 workspace)
                for object_group in self.object_groups:
                    object_name = object_group.object_name.value
                    for angle in scale_group.angles.get_selections():
                        statistics += self.run_one(
                            image_name, object_name, scale, angle, workspace)
                    if self.wants_gabor:
                        statistics += self.run_one_gabor(image_name, 
                                                         object_name, 
                                                         scale,
                                                         workspace)
        if workspace.frame is not None:
            workspace.display_data.statistics = statistics
    
    def display(self, workspace):
        figure = workspace.create_or_find_figure(title="EnhancedMeasureTexture, image cycle #%d"%(
                workspace.measurements.image_set_number),subplots=(1,1))
        figure.subplot_table(0, 0, workspace.display_data.statistics,
                             ratio=(.20,.20,.20,.20,.20))
    
    def run_one(self, image_name, object_name, scale, angle, workspace):
        """Run, computing the area measurements for a single map of objects"""
        statistics = []
        image = workspace.image_set.get_image(image_name,
                                              must_be_grayscale=True)
        objects = workspace.get_objects(object_name)
        pixel_data = image.pixel_data
        if image.has_mask:
            mask = image.mask
        else:
            mask = None
        labels = objects.segmented
        try:
            pixel_data = objects.crop_image_similarly(pixel_data)
        except ValueError:
            #
            # Recover by cropping the image to the labels
            #
            pixel_data, m1 = size_similarly(labels, pixel_data)
            if np.any(~m1):
                if mask is None:
                    mask = m1
                else:
                    mask, m2 = size_similarly(labels, mask)
                    mask[~m2] = False
            
        if np.all(labels == 0):
            for name in F_HARALICK:
                statistics += self.record_measurement(
                    workspace, image_name, object_name, 
                    str(scale) + "_" + H_TO_A[angle], name, np.zeros((0,)))
        else:
            scale_i, scale_j = self.get_angle_ij(angle, scale)
                
            for name, value in zip(F_HARALICK, Haralick(pixel_data,
                                                        labels,
                                                        scale_i,
                                                        scale_j,
                                                        mask=mask).all()):
                statistics += self.record_measurement(
                    workspace, image_name, object_name, 
                    str(scale) + "_" + H_TO_A[angle], name, value)
        return statistics

    def get_angle_ij(self, angle, scale):
        if angle == H_VERTICAL:
            return scale, 0
        elif angle == H_HORIZONTAL:
            return 0, scale
        elif angle == H_DIAGONAL:
            return scale, scale
        elif angle == H_ANTIDIAGONAL:
            return scale, -scale
        
    def localmean(self, x, y, k, cum_sum):
        nx=len(cum_sum[0])
        ny=len(cum_sum)

        hk = k / 2
        startx = int(max(0, x - hk))
        starty = int(max(0, y - hk))
        stopx = int(min(nx-1, x + hk - 1))
        stopy = int(min(ny-1, y + hk - 1))
        
        if startx == 0: left=0.0
        else: left=cum_sum[stopy,startx-1]
        if starty == 0: up=0.0
        else: up=cum_sum[starty-1,stopx]
        if startx == 0 or starty == 0: upleft=0.0
        else: upleft=cum_sum[starty-1,startx-1]  
        
        down=cum_sum[stopy,stopx]
        area=(stopy-starty+1)*(stopx-startx+1)
        mean=(down-left-up+upleft)/float(area)
        return mean 
    
    def fast_local_mean(self, Lk, pixels, cum_sum):
        '''Compute the local mean using the cumulative sum and matrix arithmetic
        
        Lk - the sampling window (I reproduced what you had in the code
        which makes an Lk of 2 be just the pixel, of 4 be a 3x3, etc.
        
        pixels - the image
        
        cum_sum - the cumulative sum of the pixels in both directions
        '''
        if Lk == 2:
            # This is the value at the pixel, no neighborhood
            return pixels
        nx=len(pixels[0])
        ny=len(pixels)           
        hLk = (Lk // 2)
        result = np.zeros(pixels.shape, pixels.dtype)
        result[hLk:-(hLk-1), hLk:-(hLk-1)] = \
            ((cum_sum[(Lk-1):, (Lk-1):] - 
              cum_sum[:-(Lk-1), (Lk-1):] -
              cum_sum[(Lk-1):, :-(Lk-1)] +
              cum_sum[:-(Lk-1), :-(Lk-1)]) / 
             ((Lk - 1)* (Lk - 1)))
        for x in  list(range(0, hLk)) +  list(range(nx-hLk+1, nx)):
            for y in range(0, ny):
                result[y, x] = self.localmean(x,y,Lk,cum_sum)
        for x in range(hLk, nx-hLk+1):
            for y in list(range(0, hLk)) + list(range(ny-hLk, ny)):
                result[y, x] = self.localmean(x,y,Lk,cum_sum)
        return result        
    
    def coarseness(self, pixels):
        nx=len(pixels[0])
        ny=len(pixels)           
        Ak=np.zeros([NB_SCALES,ny,nx])
        Ekh=np.zeros([NB_SCALES,ny,nx])
        Ekv=np.zeros([NB_SCALES,ny,nx])
        Sbest=np.zeros([ny,nx])
        
        cum_sum = np.cumsum(np.cumsum(pixels, 0), 1) 

        # 1st Step
        Lk=1
        for k in range(0, NB_SCALES):
            Lk=Lk*2 # tamura.cpp
            Ak[k, :, :] = self.fast_local_mean(Lk, pixels, cum_sum)
        
        # 2nd Step    
        Lk=1
        y, x = np.mgrid[0:ny, 0:nx]
        for k in range(0, NB_SCALES):
            Lk=Lk*2 # tamura.cpp
            x_good = (x+(Lk/2)<nx) & (x-(Lk/2)>=0)
            x1, y1 = x[x_good], y[x_good]
            Ekh[k, y1, x1]=np.fabs(Ak[k,y1,x1+(Lk//2)]-Ak[k,y1,x1-(Lk//2)])
            y_good = (y+(Lk/2)<ny) & (y-(Lk/2)>=0)
            x1, y1 = x[y_good], y[y_good]
            Ekv[k,y1,x1]=np.fabs(Ak[k,y1+(Lk//2),x1]-Ak[k,y1-(Lk//2),x1])            
                                      
        # 3rd Step
        # Here, I compare the current k for the x / y grid to
        # the current best.
        for k in range(1, NB_SCALES):
            new_best = Ekh[k, y, x] > Ekh[Sbest.astype(int), y, x]
            Sbest[new_best] = k        
        
        # As in tamura.cpp: why 32?
        #Fcoars=np.sum(Sbest)
        #if nx==32 or ny==32:
        #    Fcoars=Fcoars/((nx+1-32)*(ny+1-32))
        #else:
        #    Fcoars=Fcoars/((nx-32)*(ny-32))
        
        # As in paper:
        Fcoars=np.sum(Sbest)/(nx*ny)  
        hist, junk=np.histogram(Sbest,bins=HIST_COARS_BINS)
        hist=np.array(hist, dtype=float)
        hist=hist/max(hist)
        
        return Fcoars, hist
    
    def contrast(self, pixels):
        std=np.std(pixels)
        kurt=cpmoments.kurtosis(pixels)
        if std<0.0000000001: Fcont=0.0
        elif kurt<=0: Fcont=0.0
        else: Fcont=std/np.power(kurt,0.25)       
        return Fcont
    
    def directionality(self, pixels):
        nx=len(pixels[0])
        ny=len(pixels)
        
        dH=np.array(pixels).copy()
        dV=np.array(pixels).copy()
        
        # Prewitt's
        fH=np.array([[-1, 0, 1],[-1, 0, 1],[-1, 0, 1]])
        fV=np.array([[1, 1, 1],[0, 0, 0],[-1, -1, -1]])    
            
        # Borders are zeros, just as in convolve2D
        cH=np.zeros([ny, nx])
        cV=np.zeros([ny, nx])       
        cH[1:len(cH)-1,1:len(cH[0])-1]=scind.filters.convolve(dH,fH,mode='constant')[1:len(cH)-1,1:len(cH[0])-1]
        #sp.convolve2d(dH,fH,mode='valid')
        cV[1:len(cV)-1,1:len(cV[0])-1]=scind.filters.convolve(dV,fV,mode='constant')[1:len(cV)-1,1:len(cV[0])-1]
        #sp.convolve2d(dV,fV,mode='valid')
        
        # Borders are not only zeros
        #cH=np.zeros([ny, nx])
        #cV=np.zeros([ny, nx])         
        #cH=scind.convolve(dH,fH,mode='constant')
        #cV=scind.convolve(dV,fV,mode='constant')  
        
        theta=np.zeros([ny,nx])
        rsum=0.0 # tamura.cpp
        for y in range(0, ny):
            for x in range(0, nx):
                # Version tamura.cpp
                if cH[y,x]>=0.0001:
                    theta[y,x]=np.arctan(cV[y,x]/cH[y,x])+(np.pi/2.0+0.001)
                    rsum=rsum+(cH[y,x]*cH[y,x])+(cV[y,x]*cV[y,x])+(theta[y,x]*theta[y,x])
                else: theta[y,x]=0.0
                # Version tamura.m
                #if cH[y,x]==0 and cV[y,x]==0: theta[y,x]=0.0
                #elif cH[y,x]==0: theta[y,x]=np.pi
                #else: theta[y,x]=np.arctan(cV[y,x]/cH[y,x])+(np.pi/2.0)
        
        # Version tamura.cpp
        hist, junk=np.histogram(theta, bins=DIR_BINS)
        bmx=hist.argmax()
        hsum=0.0
        for b in range(0, DIR_BINS):
            hsum=hsum+(hist[b]*np.power(b+1-bmx,2))
        Fdir=np.fabs(np.log(hsum/(rsum+0.0000001)))        
        
        # Version tamura.m        
        #phi=[float(i)/10000 for i in range(0,31416)] 
        #hist, junk=np.histogram(theta, bins=phi)
        #hist=np.array(hist, dtype=float)
        #hist=hist/(nx*ny)
        #hist2=hist.copy()
        #for b in range(0,len(hist2)):
        #    if hist[b]<0.01: hist2[b]=0
        #bmx=hist2.argmax()
        #phiP=bmx*0.0001
        #Fdir=0.0
        #for b in range(0,len(hist2)):
        #    Fdir=Fdir+(np.power(phi[b]-phiP,2)*hist2[b])

        return Fdir
        
    def run_image(self, image_name, scale, angle, workspace):
        '''Run measurements on image'''
        statistics = []
        image = workspace.image_set.get_image(image_name,
                                              must_be_grayscale=True)
        pixel_data = image.pixel_data
        image_labels = np.ones(pixel_data.shape, int)
        if image.has_mask:
            image_labels[~ image.mask] = 0
        scale_i, scale_j = self.get_angle_ij(angle, scale)
        for name, value in zip(F_HARALICK, Haralick(pixel_data,
                                                    image_labels,
                                                    scale_i,
                                                    scale_j).all()):
            statistics += self.record_image_measurement(
                workspace, image_name, str(scale) + "_" + H_TO_A[angle],
                name, value)
        return statistics

    def run_image_tamura(self, image_name, workspace):    
        '''Run measurements on image'''
        statistics = []
        image = workspace.image_set.get_image(image_name,
                                              must_be_grayscale=True)
        pixel_data = image.pixel_data
        image_labels = np.ones(pixel_data.shape, int)
        if image.has_mask:
            image_labels[~ image.mask] = 0
               
        for name, fn in [(F_2, self.contrast),
                         (F_3, self.directionality)]:
            value = fn(pixel_data)
            statistics += self.record_image_measurement(
                workspace, image_name, "-", "%s_%s" % (F_TAMURA, name), value)           
            
        value, hist = self.coarseness(pixel_data)
        statistics += self.record_image_measurement(
                        workspace, image_name, "-", "%s_%s" % (F_TAMURA, F_1), value)        
        
        for b in range(0, HIST_COARS_BINS):
            name = "CoarsenessHist_%dBinsHist_Bin%d" % (HIST_COARS_BINS, b)
            value = hist[b]
            statistics += self.record_image_measurement(
                workspace, image_name, "-", "%s_%s" % (F_TAMURA, name), value)   
            
        return statistics
    
    def run_one_tamura(self, image_name, object_name, workspace):
        """Run, computing the area measurements for a single map of objects"""
        statistics = []
        image = workspace.image_set.get_image(image_name,
                                              must_be_grayscale=True)
        objects = workspace.get_objects(object_name)
        pixel_data = image.pixel_data
        if image.has_mask:
            mask = image.mask
        else:
            mask = None
        labels = objects.segmented
        try:
            pixel_data = objects.crop_image_similarly(pixel_data)
        except ValueError:
            #
            # Recover by cropping the image to the labels
            #
            pixel_data, m1 = size_similarly(labels, pixel_data)
            if np.any(~m1):
                if mask is None:
                    mask = m1
                else:
                    mask, m2 = size_similarly(labels, mask)
                    mask[~m2] = False
            
        if np.all(labels == 0):
            for name in F_ALL:
                statistics += self.record_measurement(workspace, image_name, 
                                                      object_name, "", "%s_%s" % (F_TAMURA, name), 
                                                      np.zeros((0,)))
        else:
            labs=np.unique(labels)
            values=np.zeros([np.max(labs)+1,2])
            for l in labs:  
                if l!=0:
                    px = pixel_data
                    px[np.where(labels != l)] = 0.0
                    values[l,0]=self.contrast(px)
                    values[l,1]=self.directionality(px)
                    statistics += self.record_measurement(
                        workspace, image_name, object_name, 
                        "-", "%s_%s" % (F_TAMURA, F_2), values[:,0])               
                    statistics += self.record_measurement(
                        workspace, image_name, object_name, 
                        "-", "%s_%s" % (F_TAMURA, F_3), values[:,1])
            
            coars = np.zeros([np.max(labs)+1])
            coars_hist=np.zeros([np.max(labs)+1,HIST_COARS_BINS])
            for l in labs:  
                if l!=0:
                    px = pixel_data
                    px[np.where(labels != l)] = 0.0 
                    coars[l], coars_hist[l,:] = self.coarseness(px) 
                    statistics += self.record_measurement(
                        workspace, image_name, object_name, 
                        "-", "%s_%s" % (F_TAMURA, F_1), coars)  
            for b in range(0,HIST_COARS_BINS):
                value = coars_hist[1:,b] 
                name = "CoarsenessHist_%dBinsHist_Bin%d" % (HIST_COARS_BINS, b)
                statistics += self.record_measurement(
                    workspace, image_name, object_name, 
                    "-", "%s_%s" % (F_TAMURA, name) , value)     
                
        return statistics
            
    def run_one_gabor(self, image_name, object_name, scale, workspace):
        objects = workspace.get_objects(object_name)
        labels = objects.segmented
        object_count = np.max(labels)
        if object_count > 0:
            image = workspace.image_set.get_image(image_name,
                                                  must_be_grayscale=True)
            pixel_data = image.pixel_data
            labels = objects.segmented
            if image.has_mask:
                mask = image.mask
            else:
                mask = None
            try:
                pixel_data = objects.crop_image_similarly(pixel_data)
                if mask is not None:
                    mask = objects.crop_image_similarly(mask)
                    labels[~mask] = 0
            except ValueError:
                pixel_data, m1 = size_similarly(labels, pixel_data)
                labels[~m1] = 0
                if mask is not None:
                    mask, m2 = size_similarly(labels, mask)
                    labels[~m2] = 0
                    labels[~mask] = 0
            pixel_data = normalized_per_object(pixel_data, labels)
            best_score = np.zeros((object_count,))
            for angle in range(self.gabor_angles.value):
                theta = np.pi * angle / self.gabor_angles.value
                g = gabor(pixel_data, labels, scale, theta)
                score_r = fix(scind.sum(g.real, labels,
                                         np.arange(object_count, dtype=np.int32)+ 1))
                score_i = fix(scind.sum(g.imag, labels,
                                         np.arange(object_count, dtype=np.int32)+ 1))
                score = np.sqrt(score_r**2+score_i**2)
                best_score = np.maximum(best_score, score)
        else:
            best_score = np.zeros((0,))
        statistics = self.record_measurement(workspace, 
                                             image_name, 
                                             object_name, 
                                             scale,
                                             F_GABOR, 
                                             best_score)
        return statistics
            
    def run_image_gabor(self, image_name, scale, workspace):
        image = workspace.image_set.get_image(image_name,
                                              must_be_grayscale=True)
        pixel_data = image.pixel_data
        labels = np.ones(pixel_data.shape, int)
        if image.has_mask:
            labels[~image.mask] = 0
        pixel_data = stretch(pixel_data, labels > 0)
        best_score = 0
        for angle in range(self.gabor_angles.value):
            theta = np.pi * angle / self.gabor_angles.value
            g = gabor(pixel_data, labels, scale, theta)
            score_r = np.sum(g.real)
            score_i = np.sum(g.imag)
            score = np.sqrt(score_r**2+score_i**2)
            best_score = max(best_score, score)
        statistics = self.record_image_measurement(workspace, 
                                                   image_name, 
                                                   scale,
                                                   F_GABOR, 
                                                   best_score)
        return statistics

    def record_measurement(self, workspace,  
                           image_name, object_name, scale,
                           feature_name, result):
        """Record the result of a measurement in the workspace's
        measurements"""
        data = fix(result)
        data[~np.isfinite(data)] = 0
        
        if scale == "-":
            workspace.add_measurement(
                object_name, 
                "%s_%s_%s" % (TEXTURE, feature_name, image_name), data)    
            statistics = [[image_name, object_name, 
                           feature_name,scale, 
                           "%f"%(d) if len(data) else "-"]
                          for d in data]            
        else:
            workspace.add_measurement(
                object_name, 
                "%s_%s_%s_%s" % (TEXTURE, feature_name,image_name, str(scale)), 
                data)
            statistics = [[image_name, object_name, 
                           "%s %s"%(aggregate_name, feature_name), scale, 
                           "%.2f"%fn(data) if len(data) else "-"]
                          for aggregate_name, fn in (("min",np.min),
                                                     ("max",np.max),
                                                     ("mean",np.mean),
                                                     ("median",np.median),
                                                     ("std dev",np.std))]
        return statistics

    def record_image_measurement(self, workspace,  
                                 image_name, scale,
                                 feature_name, result):
        """Record the result of a measurement in the workspace's
        measurements"""
        if not np.isfinite(result):
            result = 0
        
        if scale == "-":
            workspace.measurements.add_image_measurement("%s_%s_%s"%
                                                         (TEXTURE, feature_name,
                                                          image_name), result)        
        else:
            workspace.measurements.add_image_measurement("%s_%s_%s_%s"%
                                                         (TEXTURE, feature_name,
                                                          image_name, str(scale)), 
                                                         result)
        statistics = [[image_name, "-", 
                       feature_name, scale, 
                       "%.2f"%(result)]]
        return statistics  
    
    def upgrade_settings(self,setting_values,variable_revision_number,
                         module_name):
        """Adjust the setting_values for older save file versions
        
        setting_values - a list of strings representing the settings for
                         this module.
        variable_revision_number - the variable revision number of the module
                                   that saved the settings
        module_name - the name of the module that saved the settings
               
        returns the modified settings, revision number
        """
        if variable_revision_number == 1:
            #
            # Added "wants_gabor"
            #
            setting_values = setting_values[:-1] + ["Yes"] + setting_values[-1:]
            variable_revision_number = 2
        if variable_revision_number == 2:
            #
            # Added angles
            #
            image_count = int(setting_values[0])
            object_count = int(setting_values[1])
            scale_count = int(setting_values[2])
            scale_offset = 3 + image_count + object_count
            new_setting_values = setting_values[:scale_offset]
            for scale in setting_values[scale_offset:(scale_offset+scale_count)]:
                new_setting_values += [scale, H_HORIZONTAL] 
            new_setting_values += setting_values[(scale_offset+scale_count):]
            setting_values = new_setting_values
            variable_revision_number = 3
                
        return setting_values, variable_revision_number
