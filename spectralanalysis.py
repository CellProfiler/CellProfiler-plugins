import numpy as np
import scipy.ndimage, scipy.misc, scipy.signal, scipy.interpolate, scipy.linalg
import skimage.feature
from scipy.interpolate import interp1d
import warnings
import os.path
import logging
import cellprofiler.measurement
import cellprofiler.module
import cellprofiler.preferences
import cellprofiler.setting


__doc__ = """
This module measures orientation and wavelength of cardiomyocytes or other cells with sarcomeric qualities.
It makes measurements from three types of distributions for each cell: 
Orientation Mixed (object orientation distribution information), 
Distance Mixed (distribution of sizes of structures in the image), and 
Orientation Detailed (limits orientation information to structures with size close to the most common size of the original image). 
Angles are measured in degrees relative to the horizontal. Various statistics like mode, sum, variance, skewness, 
circular kurtosis, and ratio mode area (the value of the mode of the frequency distribution divided by the sum over the whole distribution) 
can be calculated from these distributions to obtain useful metrics.
Feature measurements are based on MATLAB-based software CytoSpectre.
"""

class SpectralAnalysis(cellprofiler.module.Module):
    variable_revision_number = 1

    module_name = "SpectralAnalysis"

    category = "Measurement"    
    
    def create_settings(self):
        self.input_image_name = cellprofiler.setting.ImageNameSubscriber("Input image", "None")
        self.objects_name = cellprofiler.setting.ObjectNameSubscriber("Objects name", "Nuclei")
      
    def settings(self):
        return [
            self.input_image_name, 
            self.objects_name
        ]
        
    def run(self, workspace):    
        def estimateSpectrumWOSA(I, resolution, spectralparams):
            inputsize = I.shape
            
            #Create circular 2D Hann window via linear interpolation from the 1D window
            windowlength1D = int(np.ceil(spectralparams['windowinterpolation'] * np.amax(spectralparams['windowsize']) / 2))
            window1D = np.hanning(2 * windowlength1D + 3)
            window1D = window1D[1:-1]
            windowradial = window1D[windowlength1D:]
            windowradial = np.append(windowradial, [0])
            radialpoints = np.arange(windowlength1D + 2) * 1.0 / (windowlength1D + 1)
            
            queryxi = np.tile((np.arange(spectralparams['windowsize'][0]) - (spectralparams['windowsize'][0] - 1) * 1.0 / 2) * 1.0 / ((spectralparams['windowsize'][0] - 1) / 2), (spectralparams['windowsize'][1], 1))
            queryyi = np.tile((np.arange(spectralparams['windowsize'][1]) - (spectralparams['windowsize'][1] - 1) * 1.0 / 2)[:, np.newaxis] * 1.0 / ((spectralparams['windowsize'][1] - 1) / 2), (1, spectralparams['windowsize'][0]))
            querypoints = np.sqrt(queryxi**2 + queryyi**2)
            querypoints[querypoints > 1] = 1
            window = np.interp(querypoints, radialpoints, windowradial)
            
            #Calculate number of segments, adjust overlap, calculate step size
            numsegments = np.round((inputsize - spectralparams['overlap'] * spectralparams['windowsize']) * 1.0 / (spectralparams['windowsize'] - spectralparams['overlap']*spectralparams['windowsize']) + 0.2)
            spectralparams['overlap'] = (spectralparams['windowsize'] * numsegments - inputsize) * 1.0 / (spectralparams['windowsize'] * numsegments - spectralparams['windowsize'] + np.finfo(float).eps)
            step = (1 - spectralparams['overlap']) * spectralparams['windowsize']
            
            #Calculate mean and variance of the input image. If there is only one
            #segment, the effect of the window has to be taken into account since it
            #is not cancelled during segment averaging.
            if np.all(numsegments == 1):
                directestimate = (window > 0.05 * np.amax(window)) * (I[:spectralparams['windowsize'][0], :spectralparams['windowsize'][1]])
                nonzerodirectestimate = directestimate[directestimate != 0]
                mu = np.mean(nonzerodirectestimate, axis=None)
                vari = np.var(nonzerodirectestimate, axis=None, ddof=1)
            else:
                mu = np.mean(I, axis=None)
                vari = np.var(I, axis=None, ddof=1)
                
            #Estimate spectrum for each segment, compute PSD as the squared modulus of
            #the spectral values and sum the segments.
            totalsegments = numsegments[0]*numsegments[1]
            segments = np.zeros([spectralparams['fftlength'], spectralparams['fftlength']])
            
            for segmentx in np.arange(numsegments[1]):
                indx = int(np.floor(segmentx * step[1]))
                for segmenty in np.arange(numsegments[0]):
                    indy = int(np.floor(segmenty * step[0]))
                    segments_this = np.fft.fft2(window*(I[indy:(indy + spectralparams['windowsize'][0]), indx:(indx + spectralparams['windowsize'][1])] - mu), s=[spectralparams['fftlength'], spectralparams['fftlength']])
                    segments = segments + np.absolute(segments_this)**2
                    
            #Form frequency axes
            freqbase = 1.0 / spectralparams['fftlength'] * np.arange(np.ceil(-spectralparams['fftlength'] * 1.0 / 2), np.ceil(spectralparams['fftlength'] * 1.0 / 2))            
            frequenciesy = resolution[0] * freqbase
            frequenciesx = resolution[1] * freqbase
            
            #Form PSD estimate as the mean of the individual segments (just divide by
            #the number of segments, as summing was already done within the for loop).
            PSD = segments * 1.0 / totalsegments
            
            #Shift origin to middle and remove leftmost and topmost lines of the spectrum if
            #necessary.           
            PSD = np.fft.fftshift(PSD)
            if np.mod(PSD.shape[0], 2) == 0:
                PSD = PSD[1:, :]
                frequenciesy = frequenciesy[1:]
            if np.mod(PSD.shape[1], 2) == 0:
                PSD = PSD[:,1:]
                frequenciesx = frequenciesx[1:]        
                
            #Force the sum of the spectrum to correspond to variance of the input (Parseval).
            varcorrection = vari * 1.0 / np.sum(PSD, axis=None)
            PSD = varcorrection * PSD
            return (PSD, frequenciesy, frequenciesx, totalsegments)
        
        def PSDtoPolar(PSD_cartesian, frequencies_x, frequencies_y, anglerange):      
            
            #radius of the spectral circle 
            radius = np.amax([len(frequencies_x) * 1.0 / 2, len(frequencies_y) * 1.0 / 2])
            
            #Number of points on the circle (2*pi*r)
            N_angles = int(np.ceil(anglerange * radius))
            
            # If number of frequency bins is not given, set the number so as to
            # retain or exceed the frequency bin spacing of the cartesian spectrum.
            # Zero frequency bin will be left out. The original number of frequency
            # bins should be odd i.e. zero frequency is the middle frequency.            
            N_frequencies = int(np.floor(radius))
            
            #Form vector of angles from 0 to 'anglerange'
            theta_polar = np.arange(N_angles) * 1.0 / N_angles * anglerange
            
            # Form vector of radial frequencies. Accept the lower of the maximal
            # frequencies along the two dimensions as the maximum frequency. Accept the
            # higher of the smallest positive frequencies along the two dimensions as
            # the minimum frequency. This will get rid of the zero frequency bin
            maximumfrequency = np.amin([np.amax(frequencies_x), np.amax(frequencies_y)])
            minimumfrequency = np.amax([np.amin(frequencies_x[frequencies_x > 0]), np.amin(frequencies_y[frequencies_y > 0])])
            frequencies_polar = np.linspace(minimumfrequency, maximumfrequency, num=N_frequencies)
            
            # Points on the polar spectrum.
            xpolar = np.cos(theta_polar[:, np.newaxis]) * frequencies_polar
            ypolar = np.sin(theta_polar[:, np.newaxis]) * frequencies_polar
            
            # Points on the cartesian spectrum.
            xcart, ycart = np.meshgrid(frequencies_x, frequencies_y)
            
            # Transform from cartesian to polar via bilinear interpolation,
            # while preserving total variance.
            
            interp_f = scipy.interpolate.RectBivariateSpline(frequencies_x, frequencies_y, PSD_cartesian.size * PSD_cartesian, kx=1, ky=1)
            PSD_polar = (1.0 / (N_frequencies * N_angles)) * interp_f.ev(xpolar, ypolar)
            
            # Perform scaling to counter the effect of different density of spectral
            # points at different distances from the origin.
            for ind in np.arange(len(frequencies_polar)):
                PSD_polar[:,ind] = (np.pi / 2 * frequencies_polar[ind] * 1.0 / maximumfrequency) * PSD_polar[:, ind]
            
            return (PSD_polar, frequencies_polar, theta_polar)
        
        def estimateBackgroundPolar(PSD_polar, frequencies_polar, smoothingpercentage):
            def smooth(x, y, span, method='rlowess'):
                '''
                SMOOTH  Smooth data. Z = SMOOTH(X, Y, SPAN, METHOD) 
                
                  If the smoothing method requires x to be sorted, the sorting occurs automatically.
                  smooths data Y with specified METHOD. The
                  available methods are:
                          'lowess'   - Lowess (linear fit)
                          'loess'    - Loess (quadratic fit)
                          'rlowess'  - Robust Lowess (linear fit)
                          'rloess'   - Robust Loess (quadratic fit)
                  Notes:
                  In the case of (robust) lowess and (robust) loess, it is also
                  possible to specify the SPAN as a percentage of the total number
                  of data points. When SPAN is less than or equal to 1, it is
                  treated as a percentage.
                '''
                if not (method == 'lowess' or method == 'loess' or method == 'rlowess' or method == 'rloess'):
                    raise Exception('Method must be lowess or loess or rlowess or rloess')
                
                is_x = True
                y = y.flatten()
                x = x.flatten()
                
                t = len(y)
                if t == 0:
                    raise Exception('y has length 0')
                elif len(x) != t:
                    raise Exception('x, y must be same length')
                
                if span < 1: 
                    span = np.ceil(span * t)
                idx = np.arange(t)
                
                sortx = np.any(np.diff(np.isnan(x).astype(int))<0)   # if NaNs not all at end
                if sortx or np.any(np.diff(x)<0): # sort x
                    x = np.sort(x)
                    idx = np.argsort(x)
                    y = y[idx]
                
                c = np.nan * np.ones(y.shape)
                ok = ~np.isnan(x)
                
                robust = 0
                iter_ = 5
                if method[0] == 'r':
                    robust = 1
                    method = method[1:]
                c[ok] = lowess(x[ok], y[ok], span, method, robust, iter_);
                    
                c[idx] = c
                return (c)
            #--------------------------------------------------------------------
            def lowess(x, y, span, method, robust, iter_):
                '''
                LOWESS  Smooth data using Lowess or Loess method.
                
                The difference between LOWESS and LOESS is that LOWESS uses a
                linear model to do the local fitting whereas LOESS uses a
                quadratic model to do the local fitting. Some other software
                may not have LOWESS, instead, they use LOESS with order 1 or 2 to
                represent these two smoothing methods.
                
                Reference: 
                [C79] W.S.Cleveland, "Robust Locally Weighted Regression and Smoothing
                   Scatterplots", _J. of the American Statistical Ass._, Vol 74, No. 368 
                   (Dec.,1979), pp. 829-836.
                   http://www.math.tau.ac.il/~yekutiel/MA#20seminar/Cleveland#201979.pdf
                '''
                n = len(y)
                span = np.floor(span)
                span = np.amin([span,n])
                c = y.copy();
                if span == 1:
                    return np.nan
                useLoess = False
                if method == 'loess':
                    useLoess = True
                
                diffx = np.diff(x)
                
                ynan = np.isnan(y)
                anyNans = np.any(ynan.flatten())
                seps = np.sqrt(np.finfo(float).eps)
                theDiffs = np.append(np.append(1, diffx), 1)
                
                if robust:
                    # pre-allocate space for lower and upper indices for each fit,
                    # to avoid re-computing this information in robust iterations
                    lbound = np.zeros((n, 1))
                    rbound = np.zeros((n, 1))
            
                # Compute the non-robust smooth for non-uniform x
                for i in np.arange(n):
                    # if x(i) and x(i-1) are equal we just use the old value.
                    if theDiffs[i] == 0:
                        c[i] = c[i - 1]
                        if robust:
                            lbound[i] = lbound[i - 1]
                            rbound[i] = rbound[i - 1]
                    
                    # Find nearest neighbours
                    idx = iKNearestNeighbours(span, i, x, ~ynan)
                    if robust:
                        # Need to store neighborhoods for robust loop
                        lbound[i] = np.amin(idx)
                        rbound[i] = np.amax(idx)
                    
                    if idx.size == 0:
                        c[i] = np.nan
                        
                    x1 = x[idx] - x[i] # center around current point to improve conditioning
                    d1 = np.abs(x1)
                    y1 = y[idx]
            
                    weight = iTricubeWeights(d1)
                    if np.all(weight < seps):
                        weight[:] = 1    # if all weights are 0, just skip weighting
                    
                    v = np.array([np.ones(x1.shape), x1])
                    if useLoess:
                        v = np.append(v, x1 * x1) ##ok<AGROW> There is no significant growth here
                    
                    b = solve(v, y1, weight)
                    c[i] = b[0]
            
                # now that we have a non-robust fit, we can compute the residual and do
                # the robust fit if required
                maxabsyXeps = np.amax(np.abs(y)) * np.finfo(float).eps
                if robust:
                    for k in np.arange(iter_):
                        r = y - c
                        
                        # Compute robust weights
                        rweight = iBisquareWeights(r, maxabsyXeps)
                        
                        # Find new value for each point.
                        for i in np.arange(n):
                            if i > 1 and x[i]==x[i - 1]:
                                c[i] = c[i - 1]
                            
                            idx = np.arange(int(lbound[i]), int(rbound[i] + 1))#lbound(i):rbound(i);
                            if anyNans:
                                idx = idx[~ynan[idx]]
                            
                            # check robust weights for removed points
                            if np.any(rweight[idx] <= 0):
                                idx = iKNearestNeighbours(span, i, x, (rweight > 0))
                            
                            x1 = x[idx] - x[i]
                            d1 = np.abs(x1)
                            y1 = y[idx]
                
                            weight = iTricubeWeights(d1)
                            if np.all(weight < seps):
                                weight[:] = 1    # if all weights 0, just skip weighting
                            
                            v = np.array([np.ones(x1.shape), x1])
                            if useLoess:
                                v = np.append(v, x1 * x1) ##ok<AGROW> There is no significant growth here
                            
                            # Modify the weights based on x values by multiplying them by
                            # robust weights.
                            weight = weight * rweight[idx]
                            
                            b = solve(v, y1, weight)
                            c[i] = b[0]
                return (c)
            #--------------------------------------------------------------------
            def solve(v, y1, weight):
                v = np.tile(weight, (v.shape[0], 1)) * v
                y1 = weight * y1
                if (v.ndim == 1 and v.shape[0] == 1) or (v.ndim == 2 and v.shape[0] == v.shape[1]):
                    # Square v may give infs in the \ solution, so force least squares
                    b, residuals, rank, singularValues = np.linalg.lstsq(np.transpose(np.array([v, np.zeros((1, v.shape[1]))])), np.append(y1, 0))
                else:
                    b, residuals, rank, singularValues = np.linalg.lstsq(np.transpose(v), y1) 
                return (b)
                
            #--------------------------------------------------------------------
            def iKNearestNeighbours(k, i, x, in_):
                # Find the k points from x(in) closest to x(i)
                nnz_in_ = (in_ != 0).sum()
                if nnz_in_ <= k:
                    # If we have k points or fewer, then return them all
                    idx = np.where(in_)
                else:
                    # Find the distance to the k closest point
                    d = np.abs(x - x[i])
                    ds = np.sort(d[in_])
                    dk = ds[int(k) - 1]
                    
                    # Find all points that are as close as or closer than the k closest point
                    close = (np.round(d, 6) <= np.round(dk, 6))
                    
                    # The required indices are those points that are both close and "in"
                    idx = np.where(np.logical_and(close, in_))[0]
                return (idx)
            #--------------------------------------------------------------------
            # Bi-square (robust) weight function
            def iBisquareWeights(r, myeps):
                # Convert residuals to weights using the bi-square weight function.
                # NOTE that this function returns the square root of the weights
                
                # Only use non-NaN residuals to compute median
                idx = ~np.isnan(r)
                # And bound the median away from zero
                s = np.amax([1e8 * myeps, np.median(np.abs(r[idx]))])
                # Covert the residuals to weights
                delta = iBisquare(r*1.0/(6*s))
                # Everything with NaN residual should have zero weight
                delta[~idx] = 0
                return (delta)
            
            def iBisquare(x):
                # This is this bi-square function defined at the top of the left hand
                # column of page 831 in [C79]
                # NOTE that this function returns the square root of the weights
                b = np.zeros(x.shape)
                idx = np.abs(x) < 1
                b[idx] = np.abs(1 - x[idx]**2)
                return (b)
            #--------------------------------------------------------------------
            # Tri-cubic weight function
            def  iTricubeWeights(d):
                # Convert distances into weights using tri-cubic weight function.
                # NOTE that this function returns the square-root of the weights.
                #
                # Protect against divide-by-zero. This can happen if more points than the span
                # are coincident.
                maxD = np.amax(d)
                if maxD > 0:
                    d = d * 1.0 / np.amax(d)
                w = (1 - d**3)**1.5
                return (w)
                    

            # Form polar background PSD by averaging over all angles and take logarithms.
            background_polar1D = np.mean(PSD_polar, axis=0)
            background_polar1D_log = np.log(background_polar1D)
            frequencies_polar_log = np.log(frequencies_polar)
            
            # Interpolate logarithmic spectrum to obtain equidistant points.
            frequencies_polar_log_interp = np.linspace(np.amin(frequencies_polar_log), np.amax(frequencies_polar_log), num=len(frequencies_polar_log))
            background_polar1D_log_interp = np.interp(frequencies_polar_log_interp, frequencies_polar_log,background_polar1D_log)
            
            # Perform smoothing via robust local regression using weighted linear least squares and a 1st degree polynomial model (rlowess)
            # for the interpolated logarithmic spectrum.
            smoothspectrum_interp = smooth(frequencies_polar_log_interp, background_polar1D_log_interp, smoothingpercentage, 'rlowess');
            
            # Interpolate the smoothed spectrum to get values at original logarithmic frequencies.
            smoothspectrum = np.interp(frequencies_polar_log, frequencies_polar_log_interp, smoothspectrum_interp);
            
            # Convert the smoothed logarithmic spectrum to original linear scale to
            # obtain a smooth 1D background spectrum.
            background_polar1D_smooth = np.exp(smoothspectrum);
            
            # Replicate the smooth 1D background spectrum to form a 2D background
            # spectrum.
            background_polar2D = np.tile(background_polar1D_smooth, (PSD_polar.shape[0], 1))
            return background_polar2D
        
        def checkShapesEqual(w, alpha):
            case1 = (w.ndim == 1 and alpha.ndim == 1 and len(w) != len(alpha))
            case2 = (w.ndim == 1 and alpha.ndim == 2 and (w.shape[0] != alpha.shape[0] or 1 != alpha.shape[1]))
            case3 = (w.ndim == 2 and alpha.ndim == 1 and (w.shape[0] != alpha.shape[0] or 1 != w.shape[1]))
            case4 = (w.ndim == 2 and alpha.ndim == 2 and (w.shape[0] != alpha.shape[0] or w.shape[1] != alpha.shape[1]))
            if case1 or case2 or case3 or case4:
                raise Exception('Input dimensions do not match')
        
        def circ_r(alpha, w, d, dim=0):
            '''
            Computes mean resultant vector length for circular data.
            
              Input:
                alpha	sample of angles in radians
                [w		number of incidences in case of binned angle data]
                [d    spacing of bin centers for binned data, if supplied 
                      correction factor is used to correct for bias in 
                      estimation of r, in radians (!)]
                [dim  compute along this dimension, default is 1st axis]
            
                If dim argument is specified, all other optional arguments can be
                left empty: circ_r(alpha, [], [], dim)
            
              Output:
                r		mean resultant length
            
            References:
              Statistical analysis of circular data, N.I. Fisher
              Topics in circular statistics, S.R. Jammalamadaka et al. 
              Biostatistical Analysis, J. H. Zar
            '''
            checkShapesEqual(w, alpha)
                        
            if not d:
                # per default do not apply correct for binned data
                d = 0
            
            # compute weighted sum of cos and sin of angles
            r = np.sum(w * np.exp(1j * alpha), axis=dim)
            
            # obtain length 
            r = np.absolute(r) * 1.0 / np.sum(w, axis=dim)
            
            # for data with known spacing, apply correction factor to correct for bias
            # in the estimation of r (see Zar, p. 601, equ. 26.16)
            if d != 0:
                c = d * 1.0 / 2 / np.sin(d / 2)
                r = c * r
         
            return r
            
        def circ_confmean(alpha, xi, w, d, dim=0):
            '''
              Computes the confidence limits on the mean for circular data.
            
              Input:
                alpha	sample of angles in radians
                [xi   (1-xi)-confidence limits are computed, default 0.05]
                [w		number of incidences in case of binned angle data]
                [d    spacing of bin centers for binned data, if supplied 
                      correction factor is used to correct for bias in 
                      estimation of r, in radians (!)]
                [dim  compute along this dimension, default is 1st axis]
            
              Output:
                t     mean +- d yields upper/lower (1-xi)# confidence limit
            References:
              Statistical analysis of circular data, N. I. Fisher
              Topics in circular statistics, S. R. Jammalamadaka et al. 
              Biostatistical Analysis, J. H. Zar
            '''
            checkShapesEqual(w, alpha)
                            
            # set confidence limit size to default
            if not xi:
                xi = 0.05
            
            # compute ingredients for conf. lim.
            r = circ_r(alpha, w, d, dim)
            n = np.sum(w, axis=dim)
            R = n*r
            c2 = scipy.stats.chi2.ppf((1-xi), 1)
            
            # check for resultant vector length and select appropriate formula
            t = np.zeros(r.shape)
            
            if r.size == 1:
                if r < .9 and r > np.sqrt(c2*1.0/2/n):
                    t = np.sqrt((2*n*(2*R**2-n*c2))/(4*n-c2))  # equ. 26.24
                elif r >= .9:
                    t = np.sqrt(n**2-(n**2-R**2)*np.exp(c2*1.0/n))      # equ. 26.25
                else:
                    t = np.nan
                               
            else:
                for i in np.arange(r.size):
                    if r[i] < .9 and r[i] > np.sqrt(c2*1.0/2/n[i]):
                        t[i] = np.sqrt((2*n[i]*(2*R[i]**2-n[i]*c2))/(4*n[i]-c2))  # equ. 26.24
                    elif r[i] >= .9:
                        t[i] = np.sqrt(n[i]**2-(n[i]**2-R[i]**2)*np.exp(c2*1.0/n[i]))      # equ. 26.25
                    else:
                        t[i] = np.nan
                
            # apply final transform
            t = np.arccos(t * 1.0 / R)        
            return t
    
        def circ_mean(alpha, w, dim=0):
            '''
              Computes the mean direction for circular data.
            
              Input:
                alpha	sample of angles in radians
                [w		weightings in case of binned angle data]
                [dim  compute along this dimension, default is 1st axis]
            
                If dim argument is specified, all other optional arguments can be
                left empty: circ_mean(alpha, [], dim)
            
              Output:
                mu		mean direction
                ul    upper 95# confidence limit
                ll    lower 95# confidence limit 
            
            References:
              Statistical analysis of circular data, N. I. Fisher
              Topics in circular statistics, S. R. Jammalamadaka et al. 
              Biostatistical Analysis, J. H. Zar
            '''
            checkShapesEqual(w, alpha)
                        
            # compute weighted sum of cos and sin of angles
            r = np.sum(w*np.exp(1j*alpha), axis=dim)
            
            # obtain mean in radians
            mu = np.angle(r)
            
            # confidence limits 
            t = circ_confmean(alpha, 0.05, w, [], dim)
            ul = mu + t
            ll = mu - t         
            return (mu, ul, ll)
        
        def circ_var(alpha, w, d, dim=0):
            '''
              Computes circular variance for circular data 
              (equ. 26.17/18, Zar).   
            
              Input:
                alpha	sample of angles in radians
                [w		number of incidences in case of binned angle data]
                [d    spacing of bin centers for binned data, if supplied 
                      correction factor is used to correct for bias in 
                      estimation of r]
                [dim  compute along this dimension, default is 1st axis]
            
                If dim argument is specified, all other optional arguments can be
                left empty: circ_var(alpha, [], [], dim)
            
              Output:
                S     circular variance 1-r
                s     angular variance 2*(1-r)
            
            References:
              Statistical analysis of circular data, N.I. Fisher
              Topics in circular statistics, S.R. Jammalamadaka et al. 
              Biostatistical Analysis, J. H. Zar
            '''
            if not d:
                # per default do not apply correct for binned data
                d = 0
            
            if w.size == 0:
                # if no specific weighting has been specified
                # assume no binning has taken place
                w = np.ones(alpha.shape)
            else:
                checkShapesEqual(w, alpha)
                                
            # compute mean resultant vector length
            r = circ_r(alpha, w, d, dim)
            
            # apply transformation to var
            S = 1 - r
            s = 2 * S           
            return (S, s)
 
        def circ_std(alpha, w, d, dim=0):
            '''
              Computes circular standard deviation for circular data 
              (equ. 26.20, Zar).   
            
              Input:
                alpha	sample of angles in radians
                [w		weightings in case of binned angle data]
                [d    spacing of bin centers for binned data, if supplied 
                      correction factor is used to correct for bias in 
                      estimation of r]
                [dim  compute along this dimension, default is 1st axis]
            
                If dim argument is specified, all other optional arguments can be
                left empty: circ_std(alpha, [], [], dim)
            
              Output:
                s     angular deviation
                s0    circular standard deviation
            
            References:
              Biostatistical Analysis, J. H. Zar
            '''
            if not d:
                # per default do not apply correct for binned data
                d = 0
            
            if w.size == 0:
                # if no specific weighting has been specified
                # assume no binning has taken place
                w = np.ones(alpha.shape)
            else:
                checkShapesEqual(w, alpha)
                              
            # compute mean resultant vector length
            r = circ_r(alpha, w, d, dim)
            
            s = np.sqrt(2 * (1 - r))      # 26.20
            s0 = np.sqrt(-2 * np.log(r))    # 26.21
            return (s, s0)
        
        def circ_moment(alpha, w, p=1, cent=False, dim=0):
            '''
              Calculates the complex p-th centred or non-centred moment 
              of the angular data in angle.
            
              Input:
                alpha     sample of angles
                [w        weightings in case of binned angle data]
                [p        p-th moment to be computed, default is p=1]
                [cent     if true, central moments are computed, default = false]
                [dim      compute along this dimension, default is 1st axis]
            
                If dim argument is specified, all other optional arguments can be
                left empty: circ_moment(alpha, [], [], [], dim)
            
              Output:
                mp        complex p-th moment
                rho_p     magnitude of the p-th moment
                mu_p      angle of th p-th moment
            
            
              References:
                Statistical analysis of circular data, Fisher, p. 33/34
            '''
            if w.size == 0:
                # if no specific weighting has been specified
                # assume no binning has taken place
                w = np.ones(alpha.shape)
            else:
                checkShapesEqual(w, alpha)
                            
            if cent:
                theta = np.array(circ_mean(alpha, w, dim))
                theta = theta[~np.isnan(theta)]
                theta_size = len(theta)
                alpha = circ_dist(alpha, np.tile(theta, (alpha.shape[0] / theta_size,)))
            
            n = alpha.shape[dim]
            cbar = np.sum(np.cos(p*alpha) * w, axis=dim) * 1.0 / n
            sbar = np.sum(np.sin(p*alpha) * w, axis=dim) * 1.0 / n
            mp = cbar + 1j * sbar
            
            rho_p = np.abs(mp)
            mu_p = np.angle(mp)
            return (mp, rho_p, mu_p)
        
        def circ_dist(x, y):
            '''
              Pairwise difference x_i-y_i around the circle computed efficiently.
            
              Input:
                x      sample of linear random variable
                y       sample of linear random variable or one single angle
            
              Output:
                r       matrix with differences
            
            References:
                Biostatistical Analysis, J. H. Zar, p. 651
            '''

            #condition1
            condition1 = ((x.ndim == 1 and y.ndim == 1 and len(x) != len(y)) or 
                          (x.ndim == 1 and y.ndim == 2 and x.shape[0] != y.shape[0]) or 
                          (x.ndim == 2 and y.ndim == 1 and x.shape[0] != y.shape[0]) or 
                          (x.ndim == 2 and y.ndim == 2 and x.shape[0] != y.shape[0]))
            
            #condition2
            condition2 = ((x.ndim == 1 and y.ndim == 1) or 
                          (x.ndim == 1 and y.ndim == 2 and 1 != y.shape[1]) or 
                          (x.ndim == 2 and y.ndim == 1 and 1 != x.shape[1]) or 
                          (x.ndim == 2 and y.ndim == 2 and x.shape[1] != y.shape[1]))
            
            #longest dimension of y not equal to 1
            condition3 = (y.shape[0] != 1)
            
            if condition1 and condition2 and condition3:
                raise Exception('Input dimensions do not match.')

            
            r = np.angle(np.exp(1j * x) * 1.0 / np.exp(1j * y))       
            return r
            
        def circ_skewness(alpha, w, dim=0):
            #   Calculates a measure of angular skewness.
            #
            #   Input:
            #     alpha     sample of angles
            #     [w        weightings in case of binned angle data]
            #     [dim      statistic computed along this dimension, 1st axis]
            #
            #     If dim argument is specified, all other optional arguments can be
            #     left empty: circ_skewness(alpha, [], dim)
            #
            #   Output:
            #     b         skewness (from Pewsey)
            #     b0        alternative skewness measure (from Fisher)
            #
            #   References:
            #     Pewsey, Metrika, 2004
            #     Statistical analysis of circular data, Fisher, p. 34
               
            if w.size == 0:
                # if no specific weighting has been specified
                # assume no binning has taken place
                w = np.ones(alpha.shape)
            else:
                checkShapesEqual(w, alpha)
                            
            # compute neccessary values
            R = circ_r(alpha, w, [], dim)
            theta = np.array(circ_mean(alpha, w, dim))
            theta = theta[~np.isnan(theta)]
            m2, rho2, mu2 = circ_moment(alpha, w, 2, True, dim)
            
            # compute skewness 
            theta_size = len(theta)
            
            theta2 = np.tile(theta, (alpha.shape[0] / theta_size,))
            b = np.sum(w * (np.sin(2 * (circ_dist(alpha, theta2)))), axis=dim) * 1.0 / np.sum(w, axis=dim)
            b0 = rho2 * np.sin(circ_dist(mu2, 2 * theta)) * 1.0 / (1 - R)**(3.0 / 2)    # (formula 2.29)
            return (b, b0)
        
        def circ_kurtosis(alpha, w, dim=0):
            #   Calculates a measure of angular kurtosis.
            #
            #   Input:
            #     alpha     sample of angles
            #     [w        weightings in case of binned angle data]
            #     [dim      statistic computed along this dimension, 1]
            #
            #     If dim argument is specified, all other optional arguments can be
            #     left empty: circ_kurtosis(alpha, [], dim)
            #
            #   Output:
            #     k         kurtosis (from Pewsey)
            #     k0        kurtosis (from Fisher)
            #
            #   References:
            #     Pewsey, Metrika, 2004
            #     Fisher, Circular Statistics, p. 34
            if w.size == 0:
                # if no specific weighting has been specified
                # assume no binning has taken place
                w = np.ones(alpha.shape)
            else:
                checkShapesEqual(w, alpha)
                           
            # compute mean direction
            R = circ_r(alpha, w, [], dim)
            theta = np.array(circ_mean(alpha, w, dim))
            theta = theta[~np.isnan(theta)]
            m, rho2, mu = circ_moment(alpha, w, 2, True, dim)
            m, rho, mu2 = circ_moment(alpha, w, 2, False, dim)
            
            # compute skewness 
            theta_size = len(theta)
            
            theta2 = np.tile(theta, (alpha.shape[0] / theta_size,))
            k = np.sum(w*(np.cos(2 * (circ_dist(alpha, theta2)))), axis=dim) * 1.0 / np.sum(w, axis=dim)
            k0 = (rho2*np.cos(circ_dist(mu2, 2 * theta)) - R**4)/(1 - R)**2   # (formula 2.30)
            return (k, k0)
        
        def circ_rad2ang(alpha):
            # converts values in radians to values in degree
            return alpha*1.0/np.pi*180    
        
        def analyzeOrientations(PSD_polar, rotate90=True): 
            # Calculate the orientation distribution as the marginal distribution
            # of the polar spectrum and represent as a pdf.
            marginal_polar = np.sum(PSD_polar, axis=1)
            orientation = {}  
            
            orientation['distribution'] = marginal_polar * 1.0 / np.sum(marginal_polar)
            orientation['angles'] = np.linspace(0, np.pi, PSD_polar.shape[0])
            
            # Angle doubling to get the statistics right for axial data.
            orientation['angles_full'] = np.linspace(0, 2*np.pi, PSD_polar.shape[0])
            
            # Calculate angular bin size for bias corrections.
            binspacing = orientation['angles_full'][1] - orientation['angles_full'][0]    
            
            # Rotate the distribution by 90 degrees if requested.
            if rotate90:
                bool_more = orientation['angles'] >= np.pi / 2
                bool_less = orientation['angles'] < np.pi / 2
                orientation['distribution'] = np.append(orientation['distribution'][bool_more], orientation['distribution'][bool_less])
            
            # Calculate circular statistics.
            # Mean direction.
            orientation['mean'], ul, ll = circ_mean(orientation['angles_full'], orientation['distribution'])
            orientation['mean'] = orientation['mean'] * 1.0 / 2
            # Variance.
            orientation['cvar'], s = circ_var(orientation['angles_full'], orientation['distribution'], binspacing)
            # Standard deviation.
            orientation['astd'], s0 = circ_std(orientation['angles_full'], orientation['distribution'], binspacing)
            # Skewness.
            orientation['cskew'], b0 = circ_skewness(orientation['angles_full'], orientation['distribution'])
            # Kurtosis.
            orientation['ckurt'], k0 = circ_kurtosis(orientation['angles_full'], orientation['distribution'])
            
            # Convert mean to degrees.
            orientation['mean'] = circ_rad2ang(orientation['mean'])
            if orientation['mean'] < 0:
                orientation['mean'] = orientation['mean'] + 180            
            return orientation
        
        def frequencyToWavelength(PSD_frequency, frequencies_polar):
            # Initialize.
            N_frequencies = PSD_frequency.shape[1]
            PSD_wavelength = PSD_frequency.copy()
            
            # Transform the spectrum to wavelength form while taking note of the
            # inverse square relationship between spectral densities given as functions
            # of frequency and wavelength.
            for ind in np.arange(N_frequencies):
                PSD_wavelength[:, N_frequencies - ind - 1] = PSD_frequency[:,ind] * frequencies_polar[ind]**2
            
            # Form vector of wavelengths.
            wavelengths_polar = 1.0 / frequencies_polar[np.arange(N_frequencies, 0, -1) - 1]
            return (PSD_wavelength, wavelengths_polar)
        
        def statsFromPDF(frequency, values, robust=False):
            # Find nonzero values.
            L = len(frequency)
            nonzeros = np.where(frequency != 0)[0]
            N = len(nonzeros)
            values_nonzero = values[nonzeros]
            values_nonzero = values_nonzero.flatten()
            # Normalize pdf estimate.
            frequency_norm = frequency[nonzeros] * 1.0 / np.sum(frequency[nonzeros])
            frequency_norm = frequency_norm.flatten()
            
            # If robustness used, remove the extreme quantiles according to given
            # percentage. NOTE: this is not used in CytoSpectre.
            if robust:
                robustness = robustness*1.0/100
                cumulativesum = np.cumsum(frequency_norm)
                nonzeros = np.where(robustness * 1.0 / 2 < cumulativesum and cumulativesum < 1 - robustness * 1.0 / 2)
                frequency_norm = frequency_norm[nonzeros]
                frequency_norm = frequency_norm * 1.0 / np.sum(frequency_norm)
                values_nonzero = values_nonzero[nonzeros]
            
            # Mean.
            if L > 0:
                mu = np.sum(values_nonzero * frequency_norm)
            else:
                mu = np.nan
            
            # Median.
            if L > 0:
                medzero = (np.cumsum(frequency_norm) >= 0.5 * np.sum(frequency_norm))
                medianindex = np.where(medzero.flatten())[0][0]
                medi = values_nonzero[medianindex]
            else:
                medi = np.nan
            
            # Mode.
            if L > 0:
                modezero = (frequency_norm == np.max(frequency_norm))
                maxindex = np.where(modezero)[0][0]
                mo = values_nonzero[maxindex]
            else:
                mo = np.nan
            
            # Variance and standard deviation.
            if N > 1:
                devifrommean = values_nonzero - mu
                vari = np.sum(devifrommean * devifrommean * frequency_norm)
                stdev = np.sqrt(vari)
            else:
                vari = np.nan
                stdev = np.nan
            
            # Skewness.
            if N > 1:
                skew = np.sum(devifrommean * devifrommean * devifrommean * frequency_norm) * 1.0 / (stdev * vari)
            else:
                skew = np.nan 
            
            # Kurtosis.
            if N > 1:
                kurt = np.sum(devifrommean * devifrommean * devifrommean * devifrommean * frequency_norm) * 1.0 / (vari * vari)
            else:
                kurt = np.nan          
            return (mu, medi, mo, vari, stdev, skew, kurt)
        
        def analyzeDistances(PSD_polar, frequencies_polar):
            # Calculate the spatial frequency distribution as the marginal distribution
            # of the polar spectrum and represent as a pdf.
            marginal_polar = np.sum(PSD_polar, axis=0)
            frequency = {}
            frequency['distribution'] = marginal_polar * 1.0 / np.sum(marginal_polar)
            frequency['polar'] = frequencies_polar
            
            # Convert the polar PSD to wavelength form.
            PSD_wl, polarwl = frequencyToWavelength(PSD_polar, frequency['polar'])
            # Calculate the wavelength distribution as the marginal distribution
            # of the polar wavelength spectrum.
            marginal_polar_wl = np.sum(PSD_wl, axis=0)
            
            # Interpolate to obtain uniform sampling.
            numberofpoints = (np.amax(polarwl) - np.amin(polarwl)) / (polarwl[1] - polarwl[0])
            distance = {}
            distance['polar'] = np.linspace(np.min(polarwl), np.max(polarwl), numberofpoints)
            distance['distribution'] = np.interp(distance['polar'], polarwl, marginal_polar_wl)
            
            # Calculate summary statistics.
            distance['distribution'] = distance['distribution'] * 1.0 / np.sum(distance['distribution'])
            distance['mean'], distance['median'], distance['mode'], distance['var'], distance['std'], distance['skew'], distance['kurt'] = statsFromPDF(distance['distribution'], distance['polar'], False)
            return (distance, frequency)
        
        ########################################################################
        #
        # Get some things we need from the workspace
        #
        object_set = workspace.object_set
        image_set = workspace.image_set
        measurements = workspace.measurements
        #
        # Get the objects
        #
        objects_name = self.objects_name.value
        objects = object_set.get_objects(objects_name)
        #
        # labels matrix has labels of each pixel
        # All elements sharing the same label form one region.
    
        labels = objects.segmented
    
        image_name = self.input_image_name.value
        image = image_set.get_image(image_name, must_be_grayscale=True)
        pixel_data = image.pixel_data

        if image.scale is not None:
            pixel_data = pixel_data * image.scale
        else:
            # Best guess for derived images
            pixel_data = pixel_data * 255.0        

        #
        # The indices are the integer values representing each of the objects
        # in the labels matrix. scipy.ndimage functions often take an optional
        # argument that tells them which objects should be analyzed.
        # For instance, scipy.ndimage.mean takes an input image, a labels matrix
        # and the indices. If you don't supply the indices, it will just take
        # the mean of all labeled pixels, returning a single number. list like [1, 2] for 2 objects
        #
        obj_indices = objects.indices
    
        #
        # Find the labeled pixels using labels != 0
        #
        foreground = labels != 0        
        
        #
        # Initialize default analysis settings.
        # Detail extraction default settings, used for resetting.
        analysissettings = {}
        generalsettings = {}
        generalsettings['dimensionfactor'] = 1
        
        analysissettings['default_segmentlength'] = 0.1 # Proportion of total data length.
        analysissettings['default_alpha'] = 0.05
        analysissettings['default_angleslack'] = 10 # In degrees.
        analysissettings['default_convergence_threshold'] = 1 # In degrees.
        analysissettings['default_maxiterations'] = 10
        analysissettings['default_sigma_prior_angle'] = 0.5
    
        # Color channel and camera.
        analysissettings['issegmentationon'] = 0
        analysissettings['targetchannel'] = 4
        # Camera.
        analysissettings['ismagnificationauto'] = 0
        analysissettings['magnification'] = 1.0 #40
        analysissettings['camerapixelsize'] = 1.0 #6.8 # In micrometers.
        analysissettings['imagepixelsize'] = generalsettings['dimensionfactor']*analysissettings['camerapixelsize']/analysissettings['magnification']
        analysissettings['resolution'] = 1.0/analysissettings['imagepixelsize']
        # Spectral.
        analysissettings['resolutionparameter'] = 3
        # General wavelength range.
        analysissettings['islowlimitauto'] = 1
        analysissettings['ishighlimitauto'] = 1
        analysissettings['isexcludeon'] = 0
        analysissettings['lowlimit'] = []
        analysissettings['highlimit'] = []
        analysissettings['excludelow'] = []
        analysissettings['excludehigh'] = []
        # Detail wavelength.
        analysissettings['highguess'] = []
        analysissettings['lowguess'] = []
        # Orientation correction.
        analysissettings['rotatemixed'] = 1

        result = {}
        analysispar = {}
        if True:
            analysispar['segmentlength'] = analysissettings['default_segmentlength']
            analysispar['alpha'] = analysissettings['default_alpha']
            analysispar['angleslack'] = analysissettings['default_angleslack']
            analysispar['convergence_threshold'] = analysissettings['default_convergence_threshold']
            analysispar['maxiterations'] = analysissettings['default_maxiterations']
            analysispar['sigma_prior_angle'] = analysissettings['default_sigma_prior_angle']
        
        #get image size
        analysispar['imsizey'], analysispar['imsizex'] = pixel_data.shape
        
        #set window type, 1D to 2D window interpolation ratio and overlap
        analysispar['windowinterpolation'] = 10
        analysispar['overlap'] = np.array([0.5, 0.5])
        
        #Set resolution parameter.
        resolutionsettings = {}
        resolutionsettings[1] = 1.0 / 5
        resolutionsettings[2] = 1.0 / 4
        resolutionsettings[3] = 1.0 / 3
        resolutionsettings[4] = 1.0 / 2
        resolutionsettings[5] = 1
        analysispar['resolutionparameter'] = resolutionsettings[analysissettings['resolutionparameter']]
        
        #set window size based on smaller image dimension and resolution parameter
        imsize_min = np.amin([analysispar['imsizey'], analysispar['imsizex']])
        analysispar['windowsize'] = np.round(analysispar['resolutionparameter'] * np.array([imsize_min, imsize_min]))
        analysispar['windowsize'] = np.array([int(analysispar['windowsize'][0]), int(analysispar['windowsize'][1])])
        
        #analyze whole image
        cellregion = np.ones([analysispar['imsizey'], analysispar['imsizex']])
        
        O_VALUES = {}
        D_VALUES = {}
        OD_VALUES = {}
        orientationKeys = {'mean': 'Mean', 'cvar': 'CircularVar', 'astd': 'AngularStd', 'cskew': 'CircularSkew', 'ckurt': 'CircularKurtosis', 'mode_area_ratio': 'RatioModeArea'}
        distanceKeys = {'mean': 'MeanWavelength', 'median': 'MedianWavelength', 'mode': 'ModeWavelength', 'std': 'StdWavelength', \
                        'skew': 'SkewWavelengthDistribution', 'kurt': 'KurtWavelengthDistribution', 'mode_area_ratio': 'RatioModeArea'}     
        O_KEYS = {key: 'SpectralAnalysis_OrientationMixed_'+orientationKeys[key] for key in orientationKeys}
        D_KEYS = {key: 'SpectralAnalysis_DistanceMixed_'+distanceKeys[key] for key in distanceKeys}
        OD_KEYS = {key: 'SpectralAnalysis_OrientationDetailed_'+orientationKeys[key] for key in orientationKeys}
        orientationFeatures = orientationKeys.keys()#['mean', 'cvar', 'astd', 'cskew', 'ckurt', 'mode_area_ratio']
        distanceFeatures = distanceKeys.keys()#['mean', 'median', 'mode', 'std', 'skew', 'kurt', 'mode_area_ratio']
        
        for obj_label in obj_indices:
            #
            #Obtain Polar Power Spectrum
            #
            
            #get isolated object
            object_foreground = (labels == obj_label)
            object_foreground = object_foreground * pixel_data 
            
            #FFT size
            analysispar['fftlength'] = int(2**np.amax([np.ceil(np.log2(analysispar['windowsize'][0])), 10]))
            
            #get Cartesian Power Spectrum, estimated via Welch's method 
            #WOSA: Welch's overlapped segment averaging PSD estimate
            ps = {}
            ps['raw'], ps['freq_cart'], freqx, analysispar['totalsegments'] = estimateSpectrumWOSA(object_foreground, [analysissettings['resolution'], analysissettings['resolution']], analysispar)
            
            #skip object if any values in power spectrum are nan or inf
            if np.any(np.isnan(ps['raw'])) or np.any(np.isinf(ps['raw'])):
                result = {}
                ps = {}
                break
            
            #convert power spectrum to polar
            ps['polar'], ps['freq_polar'], ps['theta_polar'] = PSDtoPolar(ps['raw'], ps['freq_cart'], ps['freq_cart'], np.pi)
            
            #reverse angle convention
            #ps['polar'] = ps['polar'][::-1, :]
            
            #
            #Estimate background
            #
            
            #background 
            ps['backgroundpolar2D'] = estimateBackgroundPolar(ps['polar'], ps['freq_polar'], analysispar['segmentlength'])
                        
            # Set lower frequency bound (i.e. higher wavelength bound).
            if analysissettings['ishighlimitauto']:
                # +11 corresponds to a 5 degree resolution at lowest frequency, +6
                # corresponds to a 10 degree resolution at lowest frequency.
                analysispar['lowestfreq'] = ps['freq_cart'][int(np.ceil(len(ps['freq_cart']) * 1.0 / 2 ) + 11 - 1)]
            elif 1.0/analysissettings['highlimit'] < np.amin(ps['freq_polar']):
                analysispar['lowestfreq'] = np.amin(ps['freq_polar'])
            elif 1.0/analysissettings['highlimit'] > np.amax(ps['freq_polar']):
                analysispar['lowestfreq'] = np.amax(ps['freq_polar'])
            else:
                analysispar['lowestfreq'] = 1.0 / analysissettings['highlimit']
            
            # Set higher frequency bound (i.e. lower wavelength bound).
            if analysissettings['islowlimitauto']:
                analysispar['highestfreq'] = np.amax(ps['freq_polar']);
            elif 1.0/analysissettings['lowlimit'] < np.amin(ps['freq_polar']):
                analysispar['highestfreq'] = np.amin(ps['freq_polar'])
            elif 1.0/analysissettings['lowlimit'] > np.amax(ps['freq_polar']):
                analysispar['highestfreq'] = np.amax(ps['freq_polar'])
            else:
                analysispar['highestfreq'] = 1.0 / analysissettings['lowlimit']
            
            # Check that upper frequency limit is higher than or equal to the lower
            # frequency limit and the band includes at least one frequency bin i.e. the
            # difference between upper and lower frequency limits is not smaller than
            # the spacing of frequency bins.
            if (analysispar['highestfreq'] - analysispar['lowestfreq']) < (ps['freq_polar'][1] - ps['freq_polar'][0]):
                # If the frequency range can be increased towards higher frequencies by
                # one bin, increase it. Otherwise increase it towards lower frequencies
                # by one bin.
                if (analysispar['lowestfreq'] + (ps['freq_polar'][1] - ps['freq_polar'][0])) <= np.amax(ps['freq_polar']):
                    analysispar['highestfreq'] = analysispar['lowestfreq'] + (ps['freq_polar'][1] - ps['freq_polar'][0])
                else:
                    analysispar['lowestfreq'] = analysispar['highestfreq'] - (ps['freq_polar'][1] - ps['freq_polar'][0])
                
            #
            #Get region of interest, mixed component 
            #

            ps['ROI_mixed'] = ps['polar'].copy()
            bool_freq_less = ps['freq_polar'] <= analysispar['lowestfreq']
            bool_freq_more = ps['freq_polar'] > analysispar['highestfreq']
            for idx in np.arange(ps['ROI_mixed'].shape[1]):
                if bool_freq_less[idx] or bool_freq_more[idx]:
                    ps['ROI_mixed'][:, idx] = 0
                       
            #
            #Orientation analysis
            #

            if ps['ROI_mixed'].size > 0:
                result['orientation_mixed'] = analyzeOrientations(ps['ROI_mixed'], rotate90 = False)
                result['orientation_mixed']['mode_area_ratio'] = np.amax(result['orientation_mixed']['distribution']) * 1.0 / np.sum(result['orientation_mixed']['distribution'])
                
            else:
                result['orientation_mixed'] = []
                
            #
            #Wavelength analysis
            #
            
            if ps['ROI_mixed'].shape > 0:
                result['distance_mixed'], frequency_mixed = analyzeDistances(ps['ROI_mixed'], ps['freq_polar'])
                result['distance_mixed']['mode_area_ratio'] = np.amax(result['distance_mixed']['distribution']) * 1.0 / np.sum(result['distance_mixed']['distribution'])
                
            else:
                result['distance_mixed'] = []
            
            #
            #Redo orientation analysis with min wavelength = mode wavelength-1 and max wavelength = mode wavelength + 1  
            #
            ps['ROI_detailed'] = ps['polar'].copy()
            lowfreq = 1.0/(result['distance_mixed']['mode'] + 1)
            highfreq = 1.0/(result['distance_mixed']['mode'] - 1)
            bool_freq_less = ps['freq_polar'] <= lowfreq
            bool_freq_more = ps['freq_polar'] > highfreq
            for idx in np.arange(ps['ROI_detailed'].shape[1]):
                if bool_freq_less[idx] or bool_freq_more[idx]:
                    ps['ROI_detailed'][:, idx] = 0            
            result['orientation_detailed'] = analyzeOrientations(ps['ROI_detailed'], rotate90=False)
            result['orientation_detailed']['mode_area_ratio'] = np.amax(result['orientation_detailed']['distribution']) * 1.0 / np.sum(result['orientation_detailed']['distribution'])
            #
            #Output
            #
            print result['orientation_mixed']
            print result['distance_mixed']
            print result['orientation_detailed']
            maxIndex = np.argmax(result['orientation_detailed']['distribution'])
            indexMargin = int(len(result['orientation_detailed']['distribution']) * 15.0 / 180)#15 degrees plus or minus
            print 'mode angle +/- 15 degrees, sum over distribution', np.sum(result['orientation_detailed']['distribution'][np.max([maxIndex-indexMargin, 0]):np.min([len(result['orientation_detailed']['distribution'])-1, maxIndex+indexMargin])])*1.0/np.sum(result['orientation_detailed']['distribution'])
            
            for key, value in result['orientation_mixed'].iteritems():
                if key in orientationFeatures:
                    if key in O_VALUES:
                        O_VALUES[key] = np.append(O_VALUES[key], value)
                    else:
                        O_VALUES[key] = np.array([value])
                
            for key, value in result['distance_mixed'].iteritems():
                if key in distanceFeatures:
                    if key in D_VALUES:
                        D_VALUES[key] = np.append(D_VALUES[key], value)
                    else:
                        D_VALUES[key] = np.array([value])
            
            for key, value in result['orientation_detailed'].iteritems():
                if key in orientationFeatures:
                    if key in OD_VALUES:
                        OD_VALUES[key] = np.append(OD_VALUES[key], value)
                    else:
                        OD_VALUES[key] = np.array([value])
            
        for i in orientationFeatures:
            measurements.add_measurement(objects_name, O_KEYS[i], O_VALUES[i])
            measurements.add_measurement(objects_name, OD_KEYS[i], OD_VALUES[i])
        for i in distanceFeatures:
            measurements.add_measurement(objects_name, D_KEYS[i], D_VALUES[i])
        
    def get_measurement_columns(self, pipeline):
        orientationKeys = ['Mean', 'CircularVar', 'AngularStd', 'CircularSkew', 'CircularKurtosis', 'RatioModeArea']
        distanceKeys = ['MeanWavelength', 'MedianWavelength', 'ModeWavelength', 'StdWavelength', 'SkewWavelengthDistribution', 'KurtWavelengthDistribution', 'RatioModeArea']
        return [(self.objects_name.value, 'SpectralAnalysis_OrientationMixed_' + key, cellprofiler.measurement.COLTYPE_FLOAT) for key in orientationKeys] + \
               [(self.objects_name.value, 'SpectralAnalysis_DistanceMixed_' + key, cellprofiler.measurement.COLTYPE_FLOAT) for key in distanceKeys] + \
               [(self.objects_name.value, 'SpectralAnalysis_OrientationDetailed_' + key, cellprofiler.measurement.COLTYPE_FLOAT) for key in orientationKeys]

    def volumetric(self):
        return False

