'''transformfilters.py - functions for applying filters to images

CellProfiler is distributed under the GNU General Public License,
but this file is licensed under the more permissive BSD license.
See the accompanying file LICENSE for details.

Copyright (c) 2003-2009 Massachusetts Institute of Technology
Copyright (c) 2009-2011 Broad Institute
All rights reserved.

Please see the AUTHORS file for credits.

Website: http://www.cellprofiler.org
'''

import numpy as np
import time
import itertools
import centrosome._filter
from centrosome.rankorder import rank_order
import scipy.ndimage as scind
from scipy.ndimage import map_coordinates, label
from scipy.ndimage import convolve, correlate1d, gaussian_filter
from scipy.ndimage import binary_dilation, binary_erosion
from scipy.ndimage import generate_binary_structure
from centrosome.smooth import smooth_with_function_and_mask
from centrosome.cpmorphology import fixup_scipy_ndimage_result as fix
from centrosome.cpmorphology import centers_of_labels
from centrosome.cpmorphology import grey_erosion, grey_reconstruction
from centrosome.cpmorphology import convex_hull_ijv, get_line_pts

def fourier_transform(image, mask=None):
    #if mask == None:
        #mask = np.ones(image.shape, bool)
    #big_mask = binary_erosion(mask,
                          #generate_binary_structure(2,2),
                          #border_value = 0)
    
    result=np.fft.fft2(image)
    #result=np.fft.fftshift(result)
    result=np.abs(result)
    # Do you want to get the modulus or the phase of the TF?
    # This is saved as an image i.e. no complex number...
    
    #result[big_mask==False] = 0
    return result

def inverse_fourier_transform(image, mask=None):
    #if mask == None:
        #mask = np.ones(image.shape, bool)
    #big_mask = binary_erosion(mask,
                          #generate_binary_structure(2,2),
                          #border_value = 0)
    
    #  This will be problematic unless your image is complex..uuurrr    
    #result=np.fft.fftshift(image)
    result=np.fft.ifft2(image)
    
    #result[big_mask==False] = 0
    return result

def check_fourier_transform(image, mask=None):
    #if mask == None:
            #mask = np.ones(image.shape, bool)
    #big_mask = binary_erosion(mask,
                            #generate_binary_structure(2,2),
                            #border_value = 0)
    
    result=np.fft.fft2(image) 
    result=np.fft.ifft2(result)
    
    #result[big_mask==False] = 0  
    return result

def simoncelli_transform_pyramid(image, scales, mask=None):  
    #if mask == None:
        #mask = np.ones(image.shape, bool)
    #big_mask = binary_erosion(mask,
                          #generate_binary_structure(2,2),
                          #border_value = 0)
    nx=len(image[0])
    ny=len(image)
    result=np.zeros([scales+1, ny, nx])
    src=np.fft.fft2(image)
    for s in range(0, scales):
        distx=np.zeros([ny, nx])
        disty=np.zeros([ny, nx])
        for x in range(0,nx):
            for y in range(0,ny):
                distx[y,x]=np.power(np.abs((nx/2)-x),2.0)
                disty[y,x]=np.power(np.abs((ny/2)-y),2.0)
        pi2=(((distx/np.power(nx/4, 2.0))+(disty/np.power(ny/4, 2.0)))<1.0)*1.0
        pi4=(((distx/np.power(nx/8, 2.0))+(disty/np.power(ny/8, 2.0)))<=1.0)*1.0
        
        dist=np.sqrt((distx/np.power(nx/2, 2.0))+(disty/np.power(ny/2, 2.0)))
        HP=(pi2*(1.0-pi4)*np.cos(0.5*np.pi*(np.log(2.0*dist)/np.log(2))))+(1-pi2)
        thenans=np.isnan(HP)
        HP[thenans]=0.0
        LP=np.sqrt(1-np.power(HP, 2.0))
        HP=np.fft.fftshift(HP)
        LP=np.fft.fftshift(LP)
        
        w=np.multiply(src, HP)
        src=np.multiply(src, LP)
        src=downsample(src)
        W=np.fft.ifft2(w)
        result[s,:ny,:nx]=W
        nx=nx/2
        ny=ny/2

    src=np.fft.ifft2(src)
    result[scales,:ny,:nx]=src
    
    #result[:, big_mask==False] = 0
    return result #TEST VERSION: result[scales, :, :]

def inverse_simoncelli_transform_pyramid(image, scale, mask=None):
    #if mask == None:
        #mask = np.ones(image.shape, bool)
    #big_mask = binary_erosion(mask,
                          #generate_binary_structure(2,2),
                          #border_value = 0)
    
    nx=len(image[0,0])
    ny=len(image[0])
    result=np.zeros([ny, nx])
    DC=image[scale,:(ny/np.power(2,scale)),:(nx/np.power(2,scale))]
    DC=np.fft.fft2(DC)
    nx=nx/np.power(2,scale-1)
    ny=ny/np.power(2,scale-1)
    for s in range(scale-1, -1, -1):
        distx=np.zeros([ny, nx])
        disty=np.zeros([ny, nx])
        for x in range(0,nx):
            for y in range(0,ny):
                distx[y,x]=np.power(np.abs((nx/2)-x),2.0)
                disty[y,x]=np.power(np.abs((ny/2)-y),2.0)
        pi2=(((distx/np.power(nx/4, 2.0))+(disty/np.power(ny/4, 2.0)))<1.0)*1.0
        pi4=(((distx/np.power(nx/8, 2.0))+(disty/np.power(ny/8, 2.0)))<=1.0)*1.0
        
        dist=np.sqrt((distx/np.power(nx/2, 2.0))+(disty/np.power(ny/2, 2.0)))
        HP=(pi2*(1.0-pi4)*np.cos(0.5*np.pi*(np.log(2.0*dist)/np.log(2))))+(1-pi2)
        thenans=np.isnan(HP)
        HP[thenans]=0.0
        LP=np.sqrt(1-np.power(HP, 2.0))
        HP=np.fft.fftshift(HP)
        LP=np.fft.fftshift(LP)         
        
        w=image[s,:ny,:nx]
        w=np.fft.fft2(w)
        DC=upsample(DC)
        w=w*HP
        DC=DC*LP*4.0
        DC=DC+w
        
        nx=nx*2
        ny=ny*2

    DC=np.fft.ifft2(DC)
    result=DC
    
    #result[:, big_mask==False] = 0
    return result

def check_simoncelli_transform_pyramid(image, scales, mask=None): 
    nx=len(image[0])
    ny=len(image)    
    WT=simoncelli_transform_pyramid(image, scales, mask)
    result=inverse_simoncelli_transform_pyramid(WT, scales, mask)
    return result

def simoncelli_transform_redundant(image, scales, mask=None):  
    #if mask == None:
        #mask = np.ones(image.shape, bool)
    #big_mask = binary_erosion(mask,
                              #generate_binary_structure(2,2),
                              #border_value = 0)
    nx=len(image[0])
    ny=len(image)
    result=np.zeros([scales+1, ny, nx])
    src=np.fft.fft2(image)
    
    distx=np.zeros([ny, nx])
    disty=np.zeros([ny, nx])
    for x in range(0,nx):
        for y in range(0,ny):
            distx[y,x]=np.power(np.abs((nx/2)-x),2.0)
            disty[y,x]=np.power(np.abs((ny/2)-y),2.0)    
    for s in range(0, scales):
        normsup=2.0*np.power(2,s+1)
        norminf=2.0*np.power(2,s+2)
        sup=(((distx/np.power(nx/normsup, 2.0))+(disty/np.power(ny/normsup, 2.0)))<1.0)*1.0
        inf=(((distx/np.power(nx/norminf, 2.0))+(disty/np.power(ny/norminf, 2.0)))<=1.0)*1.0
        
        norm=2.0*np.power(2,s)
        dist=np.sqrt((distx/np.power(nx/norm, 2.0))+(disty/np.power(ny/norm, 2.0)))
        HP=(sup*(1.0-inf)*np.cos(0.5*np.pi*(np.log(2.0*dist)/np.log(2))))+(1-sup)
        thenans=np.isnan(HP)
        HP[thenans]=0.0
        LP=np.sqrt(1-np.power(HP, 2.0))
        HP=np.fft.fftshift(HP)
        LP=np.fft.fftshift(LP)
        
        w=np.multiply(src, HP)
        src=np.multiply(src, LP)
        W=np.fft.ifft2(w)
        result[s,:ny,:nx]=W

    src=np.fft.ifft2(src)
    result[scales,:ny,:nx]=src
    
    #result[:, big_mask==False] = 0
    return result

def inverse_simoncelli_transform_redundant(image, scale, mask=None):
    #if mask == None:
        #mask = np.ones(image.shape, bool)
    #big_mask = binary_erosion(mask,
                              #generate_binary_structure(2,2),
                              #border_value = 0)

    nx=len(image[0,0])
    ny=len(image[0])
    result=np.zeros([ny, nx])
    DC=image[scale,:ny,:nx]
    DC=np.fft.fft2(DC)
    
    distx=np.zeros([ny, nx])
    disty=np.zeros([ny, nx])
    for x in range(0,nx):
        for y in range(0,ny):
            distx[y,x]=np.power(np.abs((nx/2)-x),2.0)
            disty[y,x]=np.power(np.abs((ny/2)-y),2.0)        
    for s in range(scale-1, -1, -1):
        normsup=2.0*np.power(2,s+1)
        norminf=2.0*np.power(2,s+2)
        sup=(((distx/np.power(nx/normsup, 2.0))+(disty/np.power(ny/normsup, 2.0)))<1.0)*1.0
        inf=(((distx/np.power(nx/norminf, 2.0))+(disty/np.power(ny/norminf, 2.0)))<=1.0)*1.0
        
        norm=2.0*np.power(2,s)
        dist=np.sqrt((distx/np.power(nx/norm, 2.0))+(disty/np.power(ny/norm, 2.0)))
        HP=(sup*(1.0-inf)*np.cos(0.5*np.pi*(np.log(2.0*dist)/np.log(2))))+(1-sup)
        thenans=np.isnan(HP)
        HP[thenans]=0.0
        LP=np.sqrt(1-np.power(HP, 2.0))
        HP=np.fft.fftshift(HP)
        LP=np.fft.fftshift(LP)        
        
        w=image[s,:ny,:nx]
        w=np.fft.fft2(w)
        w=w*HP
        DC=DC*LP
        DC=DC+w

    DC=np.fft.ifft2(DC)
    result=DC
    
    #result[:, big_mask==False] = 0
    return result

def check_simoncelli_transform_redundant(image, scales, mask=None): 
    nx=len(image[0])
    ny=len(image)    
    WT=simoncelli_transform_redundant(image, scales, mask)
    result=inverse_simoncelli_transform_redundant(WT, scales, mask)
    return result

def haar_transform(image, scales, mask=None):
    #if mask == None:
        #mask = np.ones(image.shape, bool)
    #big_mask = binary_erosion(mask,
                          #generate_binary_structure(2,2),
                          #border_value = 0)
   
    nx=len(image[0])
    ny=len(image)
    result=np.array(image, copy=True);
    for s in range(0, scales):
        sub=np.zeros([ny, nx])
        sub=result[:ny, :nx]
        sub=haar_analysis(sub)
        result[:ny,:nx]=sub
    nx=nx/2
    ny=ny/2
    
    #result[:, big_mask==False] = 0
    return result

def haar_analysis(image):
    alpha=np.pi/4.0
    M=np.array([[np.sin(alpha), np.cos(alpha)], [np.cos(alpha), -1.0*np.sin(alpha)]])    

    nx=len(image[0])
    ny=len(image)
    result=np.zeros([ny, nx])
    rowin=np.zeros(nx)
    rowout=np.zeros(nx)
    for y in range(0,ny):
        rowin=image[y,:]
        m=len(rowin)//2
        for n in range(0,m):
            rowout[n]=(M[0,0]*rowin[2*n])+(M[0,1]*rowin[(2*n)+1])
            rowout[n+m]=(M[1,0]*rowin[2*n])+(M[1,1]*rowin[(2*n)+1])
        result[y,:]=rowout
    
    colin=np.zeros(ny)
    colout=np.zeros(ny)
    for x in range(0,nx):
        colin=result[:,x]
        m=len(colin)//2
        for n in range(0,m):
            colout[n]=(M[0,0]*colin[2*n])+(M[0,1]*colin[(2*n)+1])
            colout[n+m]=(M[1,0]*colin[2*n])+(M[1,1]*colin[(2*n)+1])
        result[:,x]=colout
    return result

def inverse_haar_transform(image, scale, mask=None):
    #if mask == None:
        #mask = np.ones(image.shape, bool)
    #big_mask = binary_erosion(mask,
                          #generate_binary_structure(2,2),
                          #border_value = 0)
    
    nx=len(image[0])
    ny=len(image)
    result=np.array(image, copy=True)

    nx_coarse=nx/np.power(2.0,scale-1)
    ny_coarse=ny/np.power(2.0,scale-1)

    for s in range(0, scale):
        sub=np.zeros([ny_coarse, nx_coarse])
        sub=result[:ny_coarse,:nx_coarse]
        sub=haar_synthesis(sub)
        result[:ny_coarse,:nx_coarse]=sub
    nx_coarse=nx_coarse*2
    ny_coarse=ny_coarse*2

    #result[:, big_mask==False] = 0
    return result

def haar_synthesis(image):
    alpha=np.pi/4.0    
    M=np.array([[np.sin(alpha), np.cos(alpha)], [np.cos(alpha), -np.sin(alpha)]])

    nx=len(image[0])
    ny=len(image)
    result=np.zeros([ny, nx])

    colin=np.zeros(ny)
    colout=np.zeros(ny)
    for x in range(0, nx):
        colin=image[:,x]
        m=len(colin)//2
        for n in range(0, m):
            colout[2*n]=(M[0,0]*colin[n])+(M[0,1]*colin[m+n]);
            colout[(2*n)+1]=(M[1,0]*colin[n])+(M[1,1]*colin[m+n]);
        result[:,x]=colout

    rowin=np.zeros(nx)
    rowout=np.zeros(nx)
    for y in range(0, ny):
        rowin=result[y,:]
        m=len(rowin)//2
        for n in range(0, m):
            rowout[2*n]=(M[0,0]*rowin[n])+(M[0,1]*rowin[m+n]);
            rowout[(2*n)+1]=(M[1,0]*rowin[n])+(M[1,1]*rowin[m+n]);
        result[y,:]=rowout

    return result

def check_haar_transform(image, scale, mask=None):
    result=haar_transform(image, scale, mask)
    result=inverse_haar_transform(result, scale, mask)
    return result

def downsample(image):
    Nx=len(image[0])
    Ny=len(image)
    nx=Nx/2
    ny=Ny/2
    output=np.zeros([ny, nx], dtype=complex)
    output.real=0.25*(image.real[:ny,:nx]+image.real[ny:Ny,:nx]+image.real[:ny,nx:Nx]+image.real[ny:Ny,nx:Nx])
    output.imag=0.25*(image.imag[:ny,:nx]+image.imag[ny:Ny,:nx]+image.imag[:ny,nx:Nx]+image.imag[ny:Ny,nx:Nx])
    return output

def upsample(image):
    nx=len(image[0])
    ny=len(image)
    Nx=nx*2
    Ny=ny*2
    output=np.zeros([Ny, Nx], dtype=complex)
    output.real[:ny,:nx]=image.real
    output.real[ny:Ny,:nx]=image.real
    output.real[ny:Ny,nx:Nx]=image.real
    output.real[:ny,nx:Nx]=image.real
    output.imag[:ny,:nx]=image.imag
    output.imag[ny:Ny,:nx]=image.imag
    output.imag[ny:Ny,nx:Nx]=image.imag
    output.imag[:ny,nx:Nx]=image.imag
    return output

def chebyshev_transform(image, M, mask=None):
    #if mask == None:
    #mask = np.ones(image.shape, bool)
    #big_mask = binary_erosion(mask,
                              #generate_binary_structure(2,2),
                  #border_value = 0)
    #t1=time.clock()    
    nx=len(image[0])
    ny=len(image)
    if M<=0:
        M=min(nx,ny)
    
    x=np.zeros([nx])
    y=np.zeros([ny])    
    out=np.zeros([ny, M])     
    
    for i in range(0,nx):
        x[i]=2.0*float(i+1)/float(nx)-1
    Tx = chebyshev_polynomial(x, M, nx)
    for j in range(0,ny):
        y[j]=2.0*float(j+1)/float(ny)-1
    Ty = chebyshev_polynomial(y, M, ny)
    img=np.array(image).copy()
    #t2=time.clock()
    #dt=t2-t1
    #print "Elapsed time preprocessing: "+str(dt)       
    
    #t1=time.clock()
    out=chebyshev_coefficients_2D(img,Tx,M,nx,ny)
    #t2=time.clock()
    #dt=t2-t1
    #print "Elapsed time in chebyshev_coefficients_2D: "+str(dt)     
    
    #t1=time.clock()
    #img=np.zeros([M,ny])    
    img = out.transpose()
    #t2=time.clock()
    #dt=t2-t1
    #print "Elapsed time transposing matrix: "+str(dt)     	    

    #t1=time.clock()    
    out=chebyshev_coefficients_2D(img,Ty,M,ny,M)
    #t2=time.clock()
    #dt=t2-t1
    #print "Elapsed time in chebyshev_coefficients_2D: "+str(dt)   	

    #t1=time.clock() 
    W=M
    H=min(ny,M)
    result=np.zeros([H, W])
    for i in range(0,W):
        for j in range(0,H):
            result[j,i]=out[j,i]
    #t2=time.clock()
    #dt=t2-t1
    #print "Elapsed time writing results: "+str(dt)   	    
    
    #result[big_mask==False] = 0
    return result
  
def chebyshev_coefficients_2D(u2D, Tx, M, W, H):
    #
    # I kept collapsing the loops. First I put the
    # chebyshev_coefficients_1D code inside the loop
    # in chebyshev_coefficients_2D, then I looked at
    # the sum. It turned out to be the dot product of
    # the polynomial with the input (sum of last coordinates of u2D
    # times first coordinates of Tx).
    # 
    a2D = np.dot(u2D, Tx) / 2.0
    a2D[:,0]=a2D[:,0]/float(W)
    a2D[:,1:]=a2D[:,1:]*2.0/float(W) 	    
    return a2D

def chebyshev_polynomial(x, M, N):
    # Make a grid that looks like this:
    # n = [[0, 0, 0],
    #      [1, 1, 1],
    #      [2, 2, 2]]
    # m = [[0, 1, 2],
    #      [0, 1, 2],
    #      [0, 1, 2]]
    
    n, m = np.mgrid[0:N, 0:M]
    temp = np.arccos(x[n])
    temp[np.fabs(x[n]) > 1] = 0
    TMx = np.cos(temp * m)
    TMx[:, 0] = 1.0
    return TMx

# OLD CHEBY:
#def chebyshev_transform(image, M, mask=None):
    ##if mask == None:
    ##mask = np.ones(image.shape, bool)
    ##big_mask = binary_erosion(mask,
                              ##generate_binary_structure(2,2),
                  ##border_value = 0)
    
    ##t1=time.clock()    
    #nx=len(image[0])
    #ny=len(image)
    #if M<=0:
    #M=min(nx,ny)
    
    #x=np.zeros([nx])
    #y=np.zeros([ny])    
    #out=np.zeros([ny, M])     
    
    #for i in range(0,nx):
    #x[i]=2.0*float(i+1)/float(nx)-1
    #for j in range(0,ny):
    #y[j]=2.0*float(j+1)/float(ny)-1

    #img=np.array(image).copy()
    ##t2=time.clock()
    ##dt=t2-t1
    ##print "Elapsed time preprocessing: "+str(dt)       
    
    ##t1=time.clock()
    #out=chebyshev_coefficients_2D(img,x,M,nx,ny)
    ##t2=time.clock()
    ##dt=t2-t1
    ##print "Elapsed time in chebyshev_coefficients_2D: "+str(dt)     
    
    ##t1=time.clock()
    ##img=np.zeros([M,ny])    
    #for m in range(0,M):
    #for j in range(0,ny):
        #img[m,j]=out[j,m]
    ##t2=time.clock()
    ##dt=t2-t1
    ##print "Elapsed time transposing matrix: "+str(dt)     	    

    ##t1=time.clock()    
    #out=chebyshev_coefficients_2D(img,y,M,ny,M)
    ##t2=time.clock()
    ##dt=t2-t1
    ##print "Elapsed time in chebyshev_coefficients_2D: "+str(dt)   	

    ##t1=time.clock() 
    #W=M
    #H=min(ny,M)
    #result=np.zeros([H, W])
    #for i in range(0,W):
    #for j in range(0,H):
        #result[j,i]=out[j,i]
    ##t2=time.clock()
    ##dt=t2-t1
    ##print "Elapsed time writing results: "+str(dt)   	    
    
    ##result[big_mask==False] = 0
    #return result
  
#def chebyshev_coefficients_2D(u2D, x, M, W, H):
    #a2D=np.zeros([H,M])    
    #u1D=np.zeros([W])
    
    #for j in range(0,H):
    #for i in range(0,W):
        #u1D[i]=u2D[j,i]

    ##t1=time.clock()
    #a1D=chebyshev_coefficients_1D(u1D,x,M,W)
    ##t2=time.clock()
    ##dt=t2-t1
    ##print "Elapsed time in chebyshev_coefficients_1D: "+str(dt)

    #for m in range(0,M):
        #a2D[j,m]=a1D[m]

    #return a2D

#def chebyshev_coefficients_1D(u1D, x, M, N):
    ##t1=time.clock()    
    #Tx=chebyshev_polynomial(x,M,N)
    ##t2=time.clock()
    ##dt=t2-t1
    ##print "Elapsed time in chebyshev_polynomial: "+str(dt)     
    
    ## OLD:
    ##Tmx=np.zeros([N])
    #a=np.zeros([M])
    
    #for m in range(0,M):
    ## OLD:
    ##for n in range(0,N):
    ##    Tmx[n]=Tx[n,m]
    ##a[m]=0.0
    ##for n in range(0,N):
        ##a[m]=a[m]+(u1D[n]*Tmx[n]/2.0)

    #a[m]=0.0
    #for n in range(0,N):
        #a[m]=a[m]+(u1D[n]*Tx[n,m]/2.0)
    #if m==0:
        #a[m]=a[m]/float(N)
    #else:
        #a[m]=a[m]*2.0/float(N)

    #return a

#def chebyshev_polynomial(x, M, N):
    #temp=np.zeros([N,M])
    #TMx=np.zeros([N,M])
    
    #for n in range(0,N):
    #for m in range(0,M):
        #if np.fabs(x[n])>1: temp[n,m]=0
        #else: temp[n,m]=np.arccos(x[n])
        #TMx[n,m]=np.cos(temp[n,m]*m)
    #TMx[n,0]=1.0

    ## OLD:
    ##for m in range(0,M):
    ##for n in range(0,N):
        ##if np.fabs(x[n])>1: temp[n,m]=0
        ##else: temp[n,m]=np.arccos(x[n])
    ##for m in range(0,M):
    ##for n in range(0,N):
        ##TMx[n,m]=np.cos(temp[n,m]*m)
    ##for n in range(0,N):
    ##TMx[n,0]=1.0

    #return TMx
