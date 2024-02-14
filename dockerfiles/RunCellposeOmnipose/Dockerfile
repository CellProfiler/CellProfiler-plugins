FROM pytorch/pytorch:1.13.0-cuda11.6-cudnn8-runtime

RUN pip install cellpose==1.0.2
RUN pip install omnipose

RUN sed -i 's/from\ scipy\ import\ fft/from\ scipy.fftpack import\ fft/g' /opt/conda/lib/python3.9/site-packages/peakdetect/peakdetect.py

# COPY download_cellpose_models.py /
# RUN python /download_cellpose_models.py
