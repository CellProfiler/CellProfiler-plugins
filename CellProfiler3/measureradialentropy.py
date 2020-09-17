'''
<b>MeasureRadialEntropy</b> measures the variability of an image's
intensity inside a certain object
<hr>
<p>MeasureRadialEntropy divides an object into pie-shaped wedges, emanating from the centroid of the object, and
 measures either the mean, median, or integrated intensity of each.  Once the intensity
 of each wedge has been calculated, the entropy of the bin measurements is calculated. It is not guaranteed that every 
 slice has an intensity value if the centroid of an object lies outside of the object area. In these cases a NAN will be reported.</p>
'''


import numpy
import scipy.stats
import skimage.measure

import cellprofiler.module as cpm
import cellprofiler.measurement as cpmeas
import cellprofiler.setting as cps

ENTROPY = "Entropy"

class MeasurementTemplate(cpm.Module):

    module_name = "MeasureRadialEntropy"
    category = "Measurement"
    variable_revision_number = 1

    def create_settings(self):

        self.input_object_name = cps.ObjectNameSubscriber(
            "Select objects to measure", cps.NONE,
            doc="""Select the objects whose radial entropy you want to measure.""")

        self.input_image_name = cps.ImageNameSubscriber(
            "Select an image to measure", cps.NONE, doc="""Select the
            grayscale image you want to measure the entropy of.""" )

        self.bin_number=cps.Integer(
            "Input number of bins", 6, minval=3, maxval=60,
            doc="""Number of radial bins to divide your object into.  The minimum number
            of bins allowed is 3, the maximum number is 60.""")

        self.intensity_measurement=cps.Choice(
            "Which intensity measurement should be used?", ['Mean','Median','Integrated'], value='Mean',doc="""
            Whether each wedge's mean, median, or integrated intensity
            should be used to calculate the entropy.""" )

    def settings(self):
        return [self.input_image_name, self.input_object_name,
                self.intensity_measurement, self.bin_number]

    def run(self, workspace):
        measurements = workspace.measurements

        statistics = [["Entropy"]]

        workspace.display_data.statistics = statistics

        input_image_name = self.input_image_name.value

        input_object_name = self.input_object_name.value

        metric = self.intensity_measurement.value

        bins = self.bin_number.value

        image_set = workspace.image_set

        input_image = image_set.get_image(input_image_name,
                                          must_be_grayscale=True)
        pixels = input_image.pixel_data

        object_set = workspace.object_set

        objects = object_set.get_objects(input_object_name)

        labels = objects.segmented

        indexes = objects.indices

        my_props = skimage.measure.regionprops(labels)

        centers = numpy.asarray([props.centroid for props in my_props])

        feature = self.get_measurement_name(input_image_name,metric,bins)
        #Do the actual calculation
        entropy,slicemeasurements=self.slice_and_measure_intensity(pixels,labels,indexes,centers,metric,bins)
        #Add the measurement back into the workspace
        measurements.add_measurement(input_object_name,feature,entropy)
        
        for eachbin in range(bins):
            feature_bin = self.get_measurement_name_bins(input_image_name,metric,bins,eachbin+1)

            measurements.add_measurement(input_object_name,feature_bin,slicemeasurements[:,eachbin])

        emean = numpy.mean(entropy)

        statistics.append([feature, emean])
        
        #add statistics at some point
            


    ################################
    #
    # DISPLAY
    #
    def display(self, workspace, figure=None):
        statistics = workspace.display_data.statistics
        if figure is None:
            figure = workspace.create_or_find_figure(subplots=(1, 1,))
        else:
            figure.set_subplots((1, 1))
        figure.subplot_table(0, 0, statistics)


    def slice_and_measure_intensity(self, pixels, labels, indexes, centers, metric, nbins):
        '''For each object, iterate over the pixels that make up the object, assign them to a bin,
        then call calculate_entropy and return it to run.  Needs an update to numpy vector operations'''
        entropylist=[]
        slicemeasurementlist=[]
        for eachindex in range(len(indexes)):
            objects = numpy.zeros_like(pixels)
            objects[objects==0] = -1
            objects[labels==indexes[eachindex]]= pixels[labels==indexes[eachindex]]
            pixeldict={}
            objectiter=numpy.nditer(objects, flags=['multi_index'])
            while not objectiter.finished:
                if objectiter[0] != -1:
                    i1,i2=objectiter.multi_index
                    #Normalize the x,y coordinates to zero
                    center_y,center_x = centers[eachindex]
                    #Do the actual bin calculation
                    sliceno = int(numpy.ceil((numpy.pi + numpy.arctan2(i1 - center_y, i2 - center_x)) * (nbins / (2 * numpy.pi))))
                    if sliceno not in pixeldict.keys():
                        pixeldict[sliceno]=[objects[i1,i2]]
                    else:
                        pixeldict[sliceno] += [objects[i1, i2]]
                objectiter.iternext()
            # in the case that the object will not have pixels in a given slice, a value must still be given
            for sliceno in range(1,nbins+1):
                if sliceno not in pixeldict.keys():
                    pixeldict[sliceno]=[numpy.nan]

            entropy,slicemeasurements=self.calculate_entropy(pixeldict,metric)
            entropylist.append(entropy)
            slicemeasurementlist.append(slicemeasurements)
        entropyarray=numpy.array(entropylist)
        slicemeasurementarray=numpy.array(slicemeasurementlist)
        return entropyarray,slicemeasurementarray

    def calculate_entropy(self,pixeldict,metric):
        '''Calculates either the mean, median, or integrated intensity
        of each bin as per the user's request then calculates the entropy'''
        slicemeasurements=[]
        for eachslice in pixeldict.keys():
            if metric=='Mean':
                slicemeasurements.append(numpy.mean(pixeldict[eachslice]))
            elif metric=='Median':
                slicemeasurements.append(numpy.median(pixeldict[eachslice]))
            else:
                slicemeasurements.append(numpy.sum(pixeldict[eachslice]))
        slicemeasurements=numpy.array(slicemeasurements, dtype=float)
        #Calculate entropy, and let scipy handle the normalization for you
        # ignore the nan values
        entropy=scipy.stats.entropy(slicemeasurements[~numpy.isnan(slicemeasurements)])
        return entropy, slicemeasurements


    def get_feature_name(self,input_image_name,metric,bins):
        '''Return a measurement feature name '''
        return "%s_%s_%d" % (input_image_name, metric, bins)
    
    def get_feature_name_bins(self,input_image_name,metric,bins, binno):
        '''Return a measurement feature name '''
        return "%s_%s_Bin%d_of_%d" % (input_image_name, metric, binno, bins)

    def get_measurement_name(self, input_image_name, metric, bins):
        '''Return the whole measurement name'''
        return '_'.join([ENTROPY,
                         self.get_feature_name(input_image_name,metric,bins)])
    
    def get_measurement_name_bins(self, input_image_name, metric, bins, binno):
        '''Return the whole measurement name'''
        return '_'.join([ENTROPY,
                         self.get_feature_name_bins(input_image_name,metric,bins,binno)])


    def get_measurement_columns(self, pipeline):
        '''Return the column definitions for measurements made by this module'''
        input_object_name = self.input_object_name.value

        input_image_name=self.input_image_name.value
        metric = self.intensity_measurement.value
        bins = self.bin_number.value
        bincollist=[]
        for eachbin in range(bins):
            bincollist.append((input_object_name,
                 self.get_measurement_name_bins(input_image_name,metric,bins,eachbin+1),
                 cpmeas.COLTYPE_FLOAT))
        return [(input_object_name,
                 self.get_measurement_name(input_image_name,metric,bins),
                 cpmeas.COLTYPE_FLOAT)]+bincollist


    def get_categories(self, pipeline, object_name):
        """Get the categories of measurements supplied for the given object name

                pipeline - pipeline being run
                object_name - name of labels in question (or 'Images')
                returns a list of category names
                """
        if object_name == self.input_object_name:
            return [ENTROPY]
        else:
            return []


    def get_measurements(self, pipeline, object_name, category):
        """Get the measurements made on the given object in the given category"""
        if (object_name == self.input_object_name and
                    category == ENTROPY):
            bins=self.bin_number.value
            metric = self.intensity_measurement.value
            binmeaslist=[]
            for eachbin in range(bins):
                binmeaslist.append(metric+'_Bin'+str(eachbin+1)+'_of_'+str(bins))
            return ["Entropy"]+binmeaslist
        else:
            return []

