"""
<b>CalculateMoments</b> extracts moments statistics from a given distribution of pixel values.
<hr>
This module extracts a collection of quantitative measures of the shape of a distribution of pixel values. The user can use all pixels to compute the moments or can restrict to pixels within objects. If the image has a mask, only unmasked pixels will be used.

<p>This module can also </p>
                        
<h4>Available measurements</h4>
<ul>
<li><i>Mean:</i> </li>
<li><i>Standard deviation:</i> </li>
<li><i>Skewness:</i> </li>
<li><i>Kurtosis:</i> </li>
</ul>
</li>

<h3>Technical notes</h3> 
<p><b>CalculateMoments</b> computes the sample mean, standard deviation, skewness and kurtosis of a collection of N pixel values denoted by x<sub>i</sub>, i=1...N as follows. 
<ul>
<li>The mean is computed according to the usual definition and is denoted by &mu.</li>
<li>The standard deviation is computed using the unbiased estimator, which is defined as <sup>1</sup>&frasl<sub>N</sub> (&sum<sub>i=1...N</sub>  (x<sub>i</sub> - &mu)<sup>2</sup> )<sup><sup>1</sup>&frasl<sub>2</sub></sup>, where &mu is the mean. It is denoted by &sigma.</li>
<li>The skewness is computed as the third moment about the mean, scaled by the standard deviation to the third power. Formally, <sup>&mu<sub>3</sub></sup>&frasl<sub>&sigma<sup>3</sup></sub>, where &sigma is the unbiased estimator of the standard deviation and &mu<sup>3</sup> is the third central moment defined as <sup>1</sup>&frasl<sub>N</sub> &sum<sub>i=1...N</sub>  (x<sub>i</sub> - &mu)<sup>3</sup>.</li>
<li>The kurtosis is computed as the fourth moment about the mean, scaled by the standard deviation to the fourth power. Formally, <sup>&mu<sub>4</sub></sup>&frasl<sub>&sigma<sup>4<sup></sub>, where &sigma is the unbiased estimator of the standard deviation and &mu<sup>4</sup> is the fourth central moment defined as <sup>1</sup>&frasl<sub>N</sub> &sum<sub>i=1...N</sub>  (x<sub>i</sub> - &mu)<sup>4</sup>.</li>
</ul>

References
<ul>
<li>Doe, J. et al. (0000), "A very wonderful article," <i>an awesome journal</i>,
0:00-00.</li>
<li>The Frog, K. (0000). "It's not easy, being green," 
<i>Journal of the Depressed Amphibians</i> 0:00-00.</li>
</ul>
"""

import numpy as np
import scipy.ndimage as scind

import cellprofiler_core.module as cpm
import cellprofiler_core.measurement as cpmeas
import cellprofiler_core.object as cpo
import cellprofiler_core.setting as cps
from cellprofiler_core.constants.measurement import COLTYPE_FLOAT
from cellprofiler_core.setting.do_something import DoSomething
from cellprofiler_core.setting.multichoice import MultiChoice
from cellprofiler_core.setting.subscriber import ImageSubscriber, LabelSubscriber
from cellprofiler_core.utilities.core.object import size_similarly


def get_object_moment(pixels, func):
    labs=np.unique(pixels)
    moms=np.zeros([np.max(labs)+1,1])
    for l in labs:
        if l!=0:
            px=pixels[np.where(pixels==l)]
            moms[l]=func(px)
    return moms

def mean(pixels):
    return np.mean(pixels)

def std(pixels):
    return np.std(pixels, ddof=1)

def skewness(pixels):
    if len(pixels)==0:
        return 0
    
    pixels=np.array(pixels,dtype='float64')
    mean=np.mean(pixels)

    num=np.sum(np.power(pixels-mean,3))
    #num=num/(len(pixels)*len(pixels[0]))
    num=num/pixels.size
    denom=np.std(pixels)
    
    if denom==0.0: skew=0.0
    else: skew=num/(denom*denom*denom)   
    return skew

def kurtosis(pixels):
    if len(pixels)==0:
        return 0
    
    pixels=np.array(pixels,dtype='float64')
    mean=np.mean(pixels)
    
    num=np.sum(np.power(pixels-mean,4))
    #num=num/(len(pixels)*len(pixels[0]))
    num=num/pixels.size
    denom=np.std(pixels)   
    
    if denom==0.0: kurt=0.0
    else: kurt=num/(denom*denom*denom*denom)    
    return kurt

"""The category of the measurements made by this module"""
MOMENTS = "Moments"

MOM_1="Mean"
MOM_2="Standard Deviation"
MOM_3="Skewness"
MOM_4="Kurtosis"
MOM_ALL=[MOM_1, MOM_2, MOM_3, MOM_4]

MOM_TO_F={MOM_1: mean,
          MOM_2: std,
          MOM_3: skewness,
          MOM_4: kurtosis}

class CalculateMoments(cpm.Module):

    module_name = "CalculateMoments"
    category = 'Measurement'
    variable_revision_number = 1
    
    def create_settings(self):
        """Create the settings for the module at startup.
        """ 
        self.image_groups = []
        self.image_count = cps.HiddenCount(self.image_groups)
        self.add_image_cb(can_remove = False)
        self.add_images = DoSomething("", "Add another image",
                                          self.add_image_cb)
        self.image_divider = cps.Divider()  
        
        self.object_groups = []
        self.object_count = cps.HiddenCount(self.object_groups)
        self.add_object_cb(can_remove = True)
        self.add_objects = DoSomething("", "Add another object",
                                           self.add_object_cb)
        self.object_divider = cps.Divider()                
        
        self.moms=MultiChoice(
            "Moments to compute", MOM_ALL, MOM_ALL,
            doc = """Moments are statistics describing the distribution of values in the set of pixels of interest:
                <p><ul>
                <li><i>%(MOM_1)s</i> - the first image moment, which corresponds to the central value of the collection of pixels of interest.</li>
                <li><i>%(MOM_2)s</i> - the second image moment, which measures the amount of variation or dispersion of pixel values about its mean.</li>
                <li><i>%(MOM_3)s</i> - a scaled version of the third moment, which measures the asymmetry of the pixel values distribution about its mean.</li>
                <li><i>%(MOM_4)s</i> - a scaled version of the fourth moment, which measures the "peakedness" of the pixel values distribution.</li>
                </ul><p>
                Choose one or more moments to measure.""" % globals())    
        
    def settings(self):
        """The settings as they appear in the save file."""
        result = [self.image_count,self.object_count]
        for groups, elements in [(self.image_groups, ['image_name']),
                                (self.object_groups, ['object_name'])]:    
            for group in groups:
                for element in elements:
                    result+= [getattr(group,element)]  
        result+=[self.moms]
        return result
      
    def prepare_settings(self,setting_values):
        """Adjust the number of groups based on the number of
        setting_values"""    
        for count, sequence, fn in\
            ((int(setting_values[0]), self.image_groups, self.add_image_cb),
             (int(setting_values[1]), self.object_groups, self.add_object_cb)):
            del sequence[count:]
            while len(sequence) < count:
                fn()          
        
    def visible_settings(self):
        """The settings as they appear in the module viewer"""
        result = []
        for groups, add_button, div in [(self.image_groups, self.add_images, self.image_divider),
                                        (self.object_groups, self.add_objects, self.object_divider)]:
            for group in groups:
                result += group.visible_settings()
            result += [add_button, div]        
        
        result+=[self.moms]
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
                                             What did you call the grayscale images whose moments you want to calculate?"""))
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
                     What did you call the objects from which you want to calculate moments? 
                     If you only want to calculat moments of
                     the image overall, you can remove all objects using the "Remove this object" button. 
                     <p>Objects specified here will have moments computed against <i>all</i> images specfied above, which
                     may lead to image-object combinations that are unneccesary. If you
                     do not want this behavior, use multiple <b>CalculateMoments</b>
                     modules to specify the particular image-object measures that you want.</p>"""))
        if can_remove:
            group.append("remover", cps.do_something.RemoveSettingButton("", "Remove this object", self.object_groups, group))
        self.object_groups.append(group)    
    
    def validate_module(self, pipeline):
        """Make sure chosen images are selected only once"""
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

    def run(self, workspace):
        """Run, computing the measurements"""
        statistics = [[ "Image", "Object", "Measurement", "Value"]]
          
        for image_group in self.image_groups:
            image_name = image_group.image_name.value
            statistics += self.run_image(image_name, workspace)
            for object_group in self.object_groups:
                object_name = object_group.object_name.value
                statistics += self.run_object(image_name, object_name, workspace)
                 
        if workspace.frame is not None:
            workspace.display_data.statistics = statistics        

    def run_image(self, image_name, workspace):
        '''Run measurements on image'''
        statistics = []
        input_image = workspace.image_set.get_image(image_name,
                                                    must_be_grayscale = True)            
        pixels = input_image.pixel_data
        for name in self.moms.value.split(','):
            fn=MOM_TO_F[name]
            value=fn(pixels)
            statistics+=self.record_image_measurement(workspace,
                                                      image_name,
                                                      name, value)
        return statistics
    
    def run_object(self, image_name, object_name, workspace):
        statistics = []
        input_image = workspace.image_set.get_image(image_name,
                                                    must_be_grayscale = True)            
        objects = workspace.get_objects(object_name)  
        pixels = input_image.pixel_data
        if input_image.has_mask:
            mask = input_image.mask
        else:
            mask = None
        labels = objects.segmented
        try:
            pixels = objects.crop_image_similarly(pixels)
        except ValueError:
            #
            # Recover by cropping the image to the labels
            #
            pixels, m1 = size_similarly(labels, pixels)
            if np.any(~m1):
                if mask is None:
                    mask = m1
                else:
                    mask, m2 = size_similarly(labels, mask)
                    mask[~m2] = False
        
        if mask is not None:
            labels = labels.copy()
            labels[~mask] = 0   
            
        for name in self.moms.value.split(','):
            fn=MOM_TO_F[name]
            value=get_object_moment(pixels, fn)
            statistics+=self.record_measurement(workspace,
                                                image_name, object_name,
                                                name, value)        
        return statistics
            
    def is_interactive(self):
        return False
    
    def display(self, workspace):
        statistics = workspace.display_data.statistics
        figure = workspace.create_or_find_figure(title="CalculateMoments, image cycle #%d"%(
                workspace.measurements.image_set_number),subplots=(1,1))
        figure.subplot_table(0,0, statistics, ratio = (0.25, 0.25, 0.25, 0.25))
    
    def get_features(self):
        '''Return a measurement feature name'''
        return MOM_ALL

    def get_measurement_columns(self, pipeline):
        '''Get column names output for each measurement.'''
        cols = []
        for im in self.image_groups:
            for feature in self.get_features():
                cols += [("Image",
                          '%s_%s_%s' % (MOMENTS, feature, 
                                        im.image_name.value),
                          COLTYPE_FLOAT)]
                
        for ob in self.object_groups:
            for im in self.image_groups:  
                for feature in self.get_features():
                    cols += [(ob.object_name.value,
                              '%s_%s_%s' % (MOMENTS, feature, 
                                            im.image_name.value),
                              COLTYPE_FLOAT)]
                    
        return cols
    
    def get_categories(self, pipeline, object_name):
        """Get the measurement categories.
        
        pipeline - pipeline being run
        image_name - name of images in question
        returns a list of category names
        """     
        if any([object_name == og.object_name for og in self.object_groups]):
            return [MOMENTS]
        elif object_name == "Image":
            return [MOMENTS]        
        else:
            return []

    def get_measurements(self, pipeline, object_name, category):
        '''Get the measurements made on the given image in the given category
        
        pipeline - pipeline being run
        image_name - name of image being measured
        category - measurement category
        '''        
        if category in self.get_categories(pipeline, object_name):
            return self.get_features()
        return []
        
    def get_measurement_images(self, pipeline, object_name, category, measurement):
        '''Get the list of images measured
        
        pipeline - pipeline being run
        image_name - name of objects being measured
        category - measurement category
        measurement - measurement made on images
        '''
        if measurement in self.get_measurements(
            pipeline, object_name, category):
            return [x.image_name.value for x in self.image_groups]
        return []

    def record_measurement(self, workspace,  
                           image_name, object_name,
                           feature_name, result):
        """Record the result of a measurement in the workspace's
        measurements"""
        # Todo: The line below previous referred to "fix", assumed this meant the numpy version
        data = np.fix(result)
        data[~np.isfinite(data)] = 0
        workspace.add_measurement(object_name, 
                                  "%s_%s_%s" % (MOMENTS, feature_name,
                                                image_name), 
                                  data)
        statistics = [[image_name, object_name, 
                       feature_name,  
                       "%f"%(d) if len(data) else "-"]
                      for d in data]
        return statistics        
    
    def record_image_measurement(self, workspace,  
                                 image_name, feature_name, result):
        """Record the result of a measurement in the workspace's
        measurements"""
        if not np.isfinite(result):
            result = 0
        workspace.measurements.add_image_measurement("%s_%s_%s" % (MOMENTS, feature_name,
                                                                   image_name), 
                                                     result)
        statistics = [[image_name, "-", 
                       feature_name, 
                       "%f"%(result)]]
        return statistics