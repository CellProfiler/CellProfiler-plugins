FROM pytorch/pytorch:1.13.0-cuda11.6-cudnn8-runtime

RUN pip install cellpose==1.0.2
RUN pip install omnipose

# hotfix for the now-deprecated `peakdetect` package
# latest omnipose on github fixes this by no longer using `peakdetect` library, but not on pypi
RUN sed -i 's/from\ scipy\ import\ fft/from\ scipy.fftpack import\ fft/g' /opt/conda/lib/python3.9/site-packages/peakdetect/peakdetect.py
