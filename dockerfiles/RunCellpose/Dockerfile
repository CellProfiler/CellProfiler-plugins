FROM pytorch/pytorch:1.13.0-cuda11.6-cudnn8-runtime

RUN pip install numpy==1.26.4 cellpose==2.3.2

# Include if you wish the image to contain Cellpose pretrained models
COPY download_cellpose_models.py /
RUN python /download_cellpose_models.py
