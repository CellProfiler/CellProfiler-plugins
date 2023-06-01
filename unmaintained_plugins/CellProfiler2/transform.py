'''<b>ImageTemplate</b> - an example image processing module
<hr>
This is an example of a module that takes one image as an input and
produces a second image for downstream processing. You can use this as
a starting point for your own module: rename this file and put it in your
plugins directory.

The text you see here will be displayed as the help for your module. You
can use HTML markup here and in the settings text; the Python HTML control
does not fully support the HTML specification, so you may have to experiment
to get it to display correctly.
'''
#################################
#
# Imports from useful Python libraries
#
#################################

import numpy as np
from scipy.ndimage import gaussian_gradient_magnitude, correlate1d

#################################
#
# Imports from CellProfiler
#
# The package aliases are the standard ones we use
# throughout the code.
#
##################################

import cellprofiler.cpimage as cpi
import cellprofiler.cpmodule as cpm
import cellprofiler.settings as cps

from transformfilters import fourier_transform
from transformfilters import check_fourier_transform

from transformfilters import simoncelli_transform_pyramid
from transformfilters import simoncelli_transform_redundant
from transformfilters import check_simoncelli_transform_pyramid
from transformfilters import check_simoncelli_transform_redundant

from transformfilters import check_haar_transform
from transformfilters import haar_transform
from transformfilters import inverse_haar_transform

from transformfilters import chebyshev_transform

###################################
#
# Constants
#
# It's good programming practice to replace things like strings with
# constants if they will appear more than once in your program. That way,
# if someone wants to change the text, that text will change everywhere.
# Also, you can't misspell it by accident.
###################################

M_FOURIER = "Fourier"
M_TEST_FOURIER = "Check perfect reconstruction (FT)"

M_SIMONCELLI_P = "Simoncelli Wavelet transform (pyramid)"
M_SIMONCELLI_R = "Simoncelli Wavelet transform (redundant)"
M_TEST_SIMONCELLI_P = "Check perfect reconstruction (SWT pyramid)"
M_TEST_SIMONCELLI_R = "Check perfect reconstruction (SWT redundant)"

M_HAAR_T="Haar Wavelet transform"
M_HAAR_S="Haar Wavelet synthesis"
M_TEST_HAAR="Check perfect reconstruction (HWT)"

M_CHEBYSHEV_T="Chebyshev transform"

###################################
#
# The module class
#
# Your module should "inherit" from cellprofiler.cpmodule.CPModule.
# This means that your module will use the methods from CPModule unless
# you re-implement them. You can let CPModule do most of the work and
# implement only what you need.
#
###################################

class Transforms(cpm.CPModule):
    ###############################################
    #
    # The module starts by declaring the name that's used for display,
    # the category under which it is stored and the variable revision
    # number which can be used to provide backwards compatibility if
    # you add user-interface functionality later.
    #
    ###############################################
    module_name = "Transforms"
    category = "Image Processing"
    variable_revision_number = 1
    
    ###############################################
    #
    # create_settings is where you declare the user interface elements
    # (the "settings") which the user will use to customize your module.
    #
    # You can look at other modules and in cellprofiler.settings for
    # settings you can use.
    #
    ################################################
    
    def create_settings(self):
        #
        # The ImageNameSubscriber "subscribes" to all ImageNameProviders in 
        # prior modules. Modules before yours will put images into CellProfiler.
        # The ImageSubscriber gives your user a list of these images
        # which can then be used as inputs in your module.
        #
        self.input_image_name = cps.ImageNameSubscriber(
            # The text to the left of the edit box
            "Input image name:",
            # HTML help that gets displayed when the user presses the
            # help button to the right of the edit box
            doc = """This is the image that the module operates on. You can
            choose any image that is made available by a prior module.
            <br>
            <b>ImageTemplate</b> will do something to this image.
            """)
        #
        # The ImageNameProvider makes the image available to subsequent
        # modules.
        #
        self.output_image_name = cps.ImageNameProvider(
            "Output image name:",
            # The second parameter holds a suggested name for the image.
            "OutputImage",
            doc = """This is the image resulting from the operation.""")
        #
        # Here's a choice box - the user gets a drop-down list of what
        # can be done.
        #
        self.transform_choice = cps.Choice(
            "Transform choice:",
            # The choice takes a list of possibilities. The first one
            # is the default - the one the user will typically choose.
            [ M_FOURIER, M_SIMONCELLI_P, M_SIMONCELLI_R, M_TEST_FOURIER, M_TEST_SIMONCELLI_P, M_TEST_SIMONCELLI_R, M_HAAR_S, M_HAAR_T, M_TEST_HAAR, M_CHEBYSHEV_T],
            #
            # Here, in the documentation, we do a little trick so that
            # we use the actual text that's displayed in the documentation.
            #
            # %(GRADIENT_MAGNITUDE)s will get changed into "Gradient magnitude"
            # etc. Python will look in globals() for the "GRADIENT_" names
            # and paste them in where it sees %(GRADIENT_...)s
            #
            # The <ul> and <li> tags make a neat bullet-point list in the docs
            #
            doc = '''There are several transforms available:
             <ul><li><i>Fourier Transform:</i> Blabla. </li>
             <li><i>Wavelet Transform:</i> Blabla. </li>
             <li><i>Chebyshev Transform:</i> Blabla. </li></ul>'''
            % globals()                                                              
        )
        #
        # We use a float setting so that the user can give us a number
        # for the scale. The control will turn red if the user types in
        # an invalid scale.
        #
        self.scale = cps.Integer(
            "Scale:",
            # The default value is 1 - a short-range scale
            3,
            # We don't let the user type in really small values
            minval = 1,
            # or large values
            maxval = 100,
            doc = """This is a scaling factor that supplies the sigma for
            a gaussian that's used to smooth the image. The gradient is
            calculated on the smoothed image, so large scales will give
            you long-range gradients and small scales will give you
            short-range gradients""")
        
        self.M = cps.Integer(
            "Order:",
            # The default value is 1 - a short-range scale
            0,
            # We don't let the user type in really small values
            minval = 0,
            # or large values
            maxval = 50,
            doc = """This is the order of the Chebyshev Transform. A value of 0 will use the order matching the image dimensions.""")        
        
    #
    # The "settings" method tells CellProfiler about the settings you
    # have in your module. CellProfiler uses the list for saving
    # and restoring values for your module when it saves or loads a
    # pipeline file.
    #
    def settings(self):
        return [self.input_image_name, self.output_image_name,
                self.transform_choice, self.scale, self.M]

    #
    # visible_settings tells CellProfiler which settings should be
    # displayed and in what order.
    #
    # You don't have to implement "visible_settings" - if you delete
    # visible_settings, CellProfiler will use "settings" to pick settings
    # for display.
    #
    def visible_settings(self):
        result =  [self.input_image_name, self.output_image_name,
                   self.transform_choice]
        #
        # Show the user the scale only if self.wants_smoothing is checked
        #
        if self.transform_choice != M_FOURIER and self.transform_choice!= M_TEST_FOURIER and self.transform_choice!=M_CHEBYSHEV_T:
            result += [self.scale]  
      
        if self.transform_choice == M_CHEBYSHEV_T:
            result += [self.M]
            
        return result

    #
    # CellProfiler calls "run" on each image set in your pipeline.
    # This is where you do the real work.
    #
    def run(self, workspace):
        #
        # Get the input and output image names. You need to get the .value
        # because otherwise you'll get the setting object instead of
        # the string name.
        #
        input_image_name = self.input_image_name.value
        output_image_name = self.output_image_name.value
        #
        # Get the image set. The image set has all of the images in it.
        # The assert statement makes sure that it really is an image set,
        # but, more importantly, it lets my editor do context-sensitive
        # completion for the image set.
        #
        image_set = workspace.image_set
        # assert isinstance(image_set, cpi.ImageSet)
        #
        # Get the input image object. We want a grayscale image here.
        # The image set will convert a color image to a grayscale one
        # and warn the user.
        #
        input_image = image_set.get_image(input_image_name,
                                          must_be_grayscale = True)
        #
        # Get the pixels - these are a 2-d Numpy array.
        #
        pixels = input_image.pixel_data
        
        #
        #
        #
        if input_image.has_mask:
            mask = input_image.mask
        else:
            mask = np.ones(pixels.shape,bool)        
        
        if self.transform_choice == M_FOURIER:
            output_pixels = fourier_transform(pixels, mask)
        elif self.transform_choice == M_TEST_FOURIER:
            output_pixels = check_fourier_transform(pixels, mask)
        elif self.transform_choice == M_CHEBYSHEV_T:
            M=self.M.value
            output_pixels = chebyshev_transform(pixels, M, mask)
        elif self.transform_choice == M_SIMONCELLI_P or self.transform_choice == M_SIMONCELLI_R or self.transform_choice == M_TEST_SIMONCELLI_P or self.transform_choice == M_TEST_SIMONCELLI_R or self.transform_choice == M_HAAR_S or self.transform_choice == M_HAAR_T or self.transform_choice == M_TEST_HAAR:
            scale=self.scale.value
            nx=len(pixels[0])
            ny=len(pixels)
            scale_max=np.log(np.min([nx, ny]))/np.log(2.0)
            if scale>scale_max:
                print "Maximum number of scales exceeded."
                scale=int(scale_max)
            if self.transform_choice == M_SIMONCELLI_P:
                temp_output_pixels = simoncelli_transform_pyramid(pixels, scale, mask)
                sizex=nx
                sizey=((np.power(2, scale+1)-1)*ny)/(np.power(2,scale))
                #sizex=nx
                #sizey=(scale)*ny
                output_pixels=np.zeros([sizex, sizey])
                for s in range(0, scale+1):
                    output_pixels[0:nx, ((np.power(2, s)-1)*ny)/np.power(2, s-1):((np.power(2, s+1)-1)*ny)/np.power(2, s)]=temp_output_pixels[s,0:nx,0:ny/np.power(2,s)]
                    #output_pixels[0:nx, s*ny:(s+1)*ny]=temp_output_pixels[s,:,:]
            elif self.transform_choice == M_SIMONCELLI_R:
                temp_output_pixels = simoncelli_transform_redundant(pixels, scale, mask)
                sizex=nx
                sizey=(scale+1)*ny
                output_pixels=np.zeros([sizex, sizey])
                for s in range(0, scale+1):
                    output_pixels[0:nx, s*ny:(s+1)*ny]=temp_output_pixels[s,:,:]                
            elif self.transform_choice == M_TEST_SIMONCELLI_P:
                output_pixels = check_simoncelli_transform_pyramid(pixels, scale, mask)
            elif self.transform_choice == M_HAAR_T:
                output_pixels = haar_transform(pixels, scale, mask)
            elif self.transform_choice == M_HAAR_S:
                output_pixels = inverse_haar_transform(pixels, scale, mask)
            elif self.transform_choice == M_TEST_HAAR:
                output_pixels = check_haar_transform(pixels, scale, mask)                
            else:
                output_pixels = check_simoncelli_transform_redundant(pixels, scale, mask)
        else:
            raise NotImplementedError("Unimplemented transform: %s"%
                                      self.method.value)        
        
        #
        # Make an image object. It's nice if you tell CellProfiler
        # about the parent image - the child inherits the parent's
        # cropping and masking, but it's not absolutely necessary
        #
        output_image = cpi.Image(output_pixels, parent_image = input_image)
        image_set.add(output_image_name, output_image)
        
        #
        # Save intermediate results for display if the window frame is on
        #
        if workspace.frame is not None:
            workspace.display_data.input_pixels = pixels
            workspace.display_data.output_pixels = output_pixels

    #
    # is_interactive tells CellProfiler whether "run" uses any interactive
    # GUI elements. If you return False here, CellProfiler will run your
    # module on a separate thread which will make the user interface more
    # responsive.
    #
    def is_interactive(self):
        return False
    #
    # display lets you use matplotlib to display your results. 
    #
    def display(self, workspace):
        #
        # the "figure" is really the frame around the figure. You almost always
        # use figure.subplot or figure.subplot_imshow to get axes to draw on
        # so we pretty much ignore the figure.
        #
        #figure = workspace.create_or_find_figure(subplots=(2,1))
        figure = workspace.create_or_find_figure(subplots=(1,1))
        #
        # Show the user the input image
        #
        #figure.subplot_imshow_grayscale(
        #    0, 0, # show the image in the first row and column
        #    workspace.display_data.input_pixels,
        #    title = self.input_image_name.value)
        lead_subplot = figure.subplot(0,0)
        #
        # Show the user the final image
        #
        figure.subplot_imshow_grayscale(
            0, 0, # show the image in the first row and last column
            workspace.display_data.output_pixels,
            title = self.output_image_name.value,
            sharex = lead_subplot, sharey = lead_subplot)
        
