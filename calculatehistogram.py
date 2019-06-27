"""
<b>CalculateHistogram</b> outputs histograms with different numbers of bins (excluding masked pixels).
<hr>
This module computes histograms and returns the amount of pixels falling into each bins. The user can use all pixels in the image to build the histogram or can restrict to pixels within objects. If the image has a mask, only unmasked pixels will be measured.

The result is normalized from 0 to 1 by dividing all bins values by the value of the bin with the maximal number of pixels. Several different histograms can be computed. The number of bins in the histogram is always set by the user.
                     
<h4>Available measurements</h4>
<ul>
<li><i>N bins Histogram:</i> For each individual histogram, the module returns N measurements, corresponding to the (normalized) number of pixels in each of the N bins.<ul>
</ul>
</li>
"""

import numpy as np
import scipy.ndimage as scind

import cellprofiler.cpimage as cpi
import cellprofiler.cpmodule as cpm
import cellprofiler.measurements as cpmeas
import cellprofiler.objects as cpo
import cellprofiler.settings as cps
from cellprofiler.cpmath.cpmorphology import fixup_scipy_ndimage_result as fix

BINS='BinsHistBin'
HISTOGRAM ='Histogram'

def get_objects_histogram(pixels, labels, b):
    labs=np.unique(labels)
    hist=np.zeros([np.max(labs)+1,b])
    for l in labs:
        if l!=0:
            px=pixels[np.where(labels==l)]
            hist[l]=get_histogram(px, b)
    return hist

def get_histogram(pixels, b):
    if np.sum(np.iscomplex(pixels)):
        pixels=np.abs(pixels)         
    bins, junk = np.histogram(pixels, bins=b)
    bins=np.array(bins, dtype=float)
    bins=bins/np.max(bins)
    return bins

class CalculateHistogram(cpm.CPModule):
    
    module_name = "CalculateHistogram"
    category = "Measurement"
    variable_revision_number = 1
    
    def create_settings(self):
        """Create the settings for the module at startup.
        """         
        self.image_groups = []
        self.image_count = cps.HiddenCount(self.image_groups)
        self.add_image_cb(can_remove = False)
        self.add_images = cps.DoSomething("", "Add another image",
                                          self.add_image_cb)
        self.image_divider = cps.Divider()          

        self.object_groups = []
        self.object_count = cps.HiddenCount(self.object_groups)
        self.add_object_cb(can_remove = True)
        self.add_objects = cps.DoSomething("", "Add another object",
                                           self.add_object_cb)
        self.object_divider = cps.Divider()        
        
        self.bins_groups = []
        self.bins_count = cps.HiddenCount(self.bins_groups)
        self.add_bins_cb(can_remove = False)
        self.add_bins = cps.DoSomething("", "Add another histogram",
                                        self.add_bins_cb)
        #self.bins_divider = cps.Divider()        
        
    def settings(self):     
        """The settings as they appear in the save file."""
        result = [self.image_count,self.object_count, self.bins_count]
        for groups, elements in [(self.image_groups, ['image_name']),
                                (self.object_groups, ['object_name']),
                                (self.bins_groups, ['bins'])]:    
            for group in groups:
                for element in elements:
                    result += [getattr(group, element)]
        return result        
   
    def prepare_settings(self,setting_values):      
        """Adjust the number of object groups based on the number of
        setting_values"""
        for count, sequence, fn in\
            ((int(setting_values[0]), self.image_groups, self.add_image_cb),
             (int(setting_values[1]), self.object_groups, self.add_object_cb),
             (int(setting_values[2]), self.bins_groups, self.add_bins_cb)):
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
        
        for group in self.bins_groups:
            result += group.visible_settings()         
        result += [self.add_bins]
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
                     cps.ImageNameSubscriber("Select an image to measure","None", 
                                             doc="""
                                             What did you call the grayscale images whose histogram you want to calculate?"""))
        if can_remove:
            group.append("remover", cps.RemoveSettingButton("", "Remove this image", self.image_groups, group))
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
                     cps.ObjectNameSubscriber("Select objects to measure","None", doc="""
                     What did you call the objects whose histogram you want to calculate? 
                     If you only want to calculate the histogram 
                     for the image overall, you can remove all objects using the "Remove this object" button. 
                     <p>Objects specified here will have their
                     histogram calculated against <i>all</i> images specified above, which
                     may lead to image-object combinations that are unneccesary. If you
                     do not want this behavior, use multiple <b>CalculateHistogram</b>
                     modules to specify the particular image-object measures that you want.</p>"""))
        if can_remove:
            group.append("remover", cps.RemoveSettingButton("", "Remove this object", self.object_groups, group))
        self.object_groups.append(group)

    def add_bins_cb(self, can_remove = True):       
        '''Add an histogram to the bin_groups collection
        
        can_delete - set this to False to keep from showing the "remove"
                     button for histograms that must be present.
        '''
        group = cps.SettingsGroup()
        if can_remove:
            group.append("divider", cps.Divider(line=False))
        group.append('bins', 
                     cps.Integer("Number of bins",
                                 len(self.bins_groups)+3,
                                 doc="""How much bins do you want in your histogram? You can calculate several histograms with different number of bins using the "Add another histogram" button."""))
                                
        if can_remove:
            group.append("remover", cps.RemoveSettingButton("", "Remove this histogram", self.bins_groups, group))
        self.bins_groups.append(group)  
        
    def validate_module(self, pipeline):          
        """Make sure chosen objects, images and histograms are selected only once"""
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
            
        bins = set()
        for group in self.bins_groups:
            if group.bins.value in bins:
                raise cps.ValidationError(
                    "%s has already been selected" %group.bins.value,
                    group.bins)
            bins.add(group.bins.value)       
    
    def run(self, workspace):          
        """Run, computing the measurements"""
        statistics = [ ["Image", "Object", "Measurement", "Value"] ]  
        
        for image_group in self.image_groups:
            image_name = image_group.image_name.value
            for bins_group in self.bins_groups:
                bins = bins_group.bins.value
                statistics += self.run_image(image_name, bins, 
                                             workspace)                               
                    
                for object_group in self.object_groups:
                    object_name = object_group.object_name.value
                    statistics += self.run_object(image_name, object_name, 
                                                  bins, workspace)
                   
        if workspace.frame is not None:
            workspace.display_data.statistics = statistics      

    def run_image(self, image_name, bins, workspace):
        '''Run measurements on image'''
        statistics = []
        image = workspace.image_set.get_image(image_name,
                                              must_be_grayscale=True)
        pixel_data = image.pixel_data
        image_labels = np.ones(pixel_data.shape, int)
        if image.has_mask:
            image_labels[~ image.mask] = 0
            
        hist = get_histogram(pixel_data, bins)
        for b in range(0,bins):
            value=hist[b]
            statistics += self.record_image_measurement(
                workspace, image_name, str(bins) + BINS + str(b), value) 
        return statistics
        
    def run_object(self, image_name, object_name, bins, workspace):
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
            pixel_data, m1 = cpo.size_similarly(labels, pixel_data)
            if np.any(~m1):
                if mask is None:
                    mask = m1
                else:
                    mask, m2 = cpo.size_similarly(labels, mask)
                    mask[~m2] = False
        
        if mask is not None:
            labels = labels.copy()
            labels[~mask] = 0    

        hist = get_objects_histogram(pixel_data, labels, bins)
        if np.all(labels == 0):
            for b in range(0,bins):
                statistics += self.record_measurement(
                    workspace, image_name, object_name, 
                    str(bins) + BINS + str(b), np.zeros((0,)))
        else:
            for b in range(0,bins):
                value=hist[:,b]  
                statistics += self.record_measurement(
                    workspace, image_name, object_name, 
                    str(bins) + BINS + str(b), value)
            
        return statistics           

    def is_interactive(self):
        return False
    
    def display(self, workspace):        
        statistics = workspace.display_data.statistics
        figure = workspace.create_or_find_figure(title="CalculateHistogram, image cycle #%d"%(
            workspace.measurements.image_set_number),subplots=(1,1))
                        
        figure.subplot_table(0,0, statistics, ratio = (0.25, 0.25, 0.25, 0.25))
    
    def get_features(self,bins):         
        '''Return a measurement feature name'''
        name=[]
        for b in range(0,bins):
            name+=["%dBinsHistBin%d" % (bins, b)]
        return name
    
    def get_measurement_columns(self, pipeline):             
        '''Get column names output for each measurement.'''
        cols = []
        for im in self.image_groups:
            for bn in self.bins_groups:
                for feature in self.get_features(bn.bins.value):
                    cols += [(cpmeas.IMAGE,
                              '%s_%s_%s' % (
                                  HISTOGRAM, feature, 
                                  im.image_name.value),
                              cpmeas.COLTYPE_FLOAT)]
                            
        for ob in self.object_groups:
            for im in self.image_groups:
                for bn in self.bins_groups:
                    for feature in self.get_features(bn.bins.value):
                        cols += [(ob.object_name.value,
                                  '%s_%s_%s' % (
                                      HISTOGRAM, feature, 
                                      im.image_name.value),
                                  cpmeas.COLTYPE_FLOAT)]    
                        
        return cols        
    
    def get_categories(self,pipeline, object_name):         
        """Get the measurement categories supplied for the given object name.
        
        pipeline - pipeline being run
        object_name - name of labels in question (or 'Images')
        returns a list of category names
        """
        if any([object_name == og.object_name for og in self.object_groups]):
            return [HISTOGRAM]
        elif object_name == cpmeas.IMAGE:
            return [HISTOGRAM]
        else:
            return []    
    
    def get_measurements(self, pipeline, object_name, category):           
        '''Get the measurements made on the given object in the given category
        
        pipeline - pipeline being run
        object_name - name of objects being measured
        category - measurement category
        '''
        if category in self.get_categories(pipeline, object_name):
            return [self.get_features(b.bins.value) for b in self.bins_groups]
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
    
    def get_measurement_bins(self, pipeline, object_name, category, 
                               measurement, image_name):        
        '''Get the list of histograms that were computed

        pipeline - pipeline being run
        object_name - name of objects being measured
        category - measurement category
        measurement - name of measurement made
        image_name - name of image that was measured
        '''
        if len(self.get_measurement_images(pipeline, object_name, category,
                                           measurement)) > 0:
            
            return sum(["%d" % (x.bins.value) for x in self.bins_groups], [])
        return []      

    def record_measurement(self, workspace,  
                           image_name, object_name,
                           feature_name, result):         
        """Record the result of a measurement in the workspace's
        measurements"""
        data = fix(result)
        data[~np.isfinite(data)] = 0
        workspace.add_measurement(object_name, 
                                  "%s_%s_%s" % (HISTOGRAM, feature_name,
                                                image_name), 
                                  data)
        statistics = [[image_name, object_name, 
                      feature_name,  
                      "%f"%(d) if len(data) else "-"]
                      for d in data]
        return statistics
    
    def record_image_measurement(self, workspace,  
                                 image_name,
                                 feature_name, result):              
        """Record the result of a measurement in the workspace's
        measurements"""
        if not np.isfinite(result):
            result = 0
        workspace.measurements.add_image_measurement("%s_%s_%s"%
                                                     (HISTOGRAM, feature_name,
                                                      image_name), 
                                                     result)
        statistics = [[image_name, "-", 
                       feature_name, 
                       "%f"%(result)]]
        return statistics