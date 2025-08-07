FROM pytorch/pytorch:2.7.1-cuda11.8-cudnn9-devel

RUN pip install numpy==1.26.4 cellpose==4.0.6

# Include if you wish the image to contain Cellpose pretrained models
COPY download_cellpose_models.py /
RUN python /download_cellpose_models.py
