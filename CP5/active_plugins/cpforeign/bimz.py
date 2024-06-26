import numpy as np
import logging

from bioimageio.spec import InvalidDescr, load_description
from bioimageio.spec.model.v0_5 import ModelDescr
import bioimageio.core.prediction as bi_pred

from skimage.filters import threshold_otsu
from skimage.measure import label
from skimage.morphology import closing, square
from skimage.segmentation import clear_border

from server import ForeignToolClient

logger = logging.getLogger(__name__)

# https://bioimage.io/#/?tags=affable-shark&id=10.5281%2Fzenodo.5764892
MODEL_ID = "affable-shark"
MODEL_DOI = "10.5281/zenodo.11092561"

def load_model():
    loaded_description = load_description(MODEL_ID)
    if isinstance(loaded_description, InvalidDescr):
        raise ValueError(f"Failed to load {MODEL_ID}")
    elif not isinstance(loaded_description, ModelDescr):
        raise ValueError("This notebook expects a model 0.5 description")

    model = loaded_description
    example_model_id = model.id
    assert example_model_id is not None

    try:
        descr = load_description(MODEL_ID)
    except InvalidDescr as e:
        logger.error(f"Invalid description: {e}")
        return None

    return descr

def predict(input_image, model):
    out = bi_pred.predict(model=model, inputs={'input0': input_image}, skip_postprocessing=True, skip_preprocessing=True)
    return np.array(out.members['output0'].data[0])

def run(image_data, image_header):
    model = load_model()

    logger.debug("loaded model")

    # scaled image
    im = image_data.copy()
    logger.debug(f"provided image of shape {im.shape}, type {im.dtype}")
    # im = (image_data / np.iinfo(image_data.dtype).max).astype(np.float32)

    pad_y = (64 - image_data.shape[0] % 64) % 64
    pad_x = (64 - image_data.shape[1] % 64) % 64
    # padded image
    im = np.pad(im, ((0, pad_y), (0, pad_x)), mode='constant', constant_values=0)
    logger.debug(f"padded image of shape {im.shape}, type {im.dtype}")

    # input image
    im = im.reshape([1,1,im.shape[0],im.shape[1]])
    logger.debug(f"input image of shape {im.shape}, type {im.dtype}")

    # output image
    logger.debug("running prediction")
    res = predict(im, model)
    del im
    logger.debug(f"output image of shape {res.shape}, dtype {res.dtype}")

    # unpadded result
    res = res[:, :image_data.shape[0], :image_data.shape[1]]
    logger.debug(f"de-padded output image of shape {res.shape}, dtype {res.dtype}")

    # just the foreground probabilities, ignore boundaries
    res = res[0]
    logger.debug(f"using only fg prob of shape {res.shape}, dtype {res.dtype}")

    # threshold above certain prob
    thresh = threshold_otsu(res)
    logger.debug(f"threshold image shape {thresh.shape}, dtype {thresh.dtype}")
    # make binary, with closing (remove small holes in fg with dilate then erode)
    bw = closing(res > thresh, square(3))
    logger.debug(f"binary image of shape {bw.shape}, type {bw.dtype}")

    # remove border cells
    # cleared = clear_border(bw)
    # labels = label(cleared)

    # convert to labels
    labels = label(bw)
    logger.debug(f"labels of shape {labels.shape}, dtype {labels.dtype}")

    return labels


def main():
    client = ForeignToolClient(7878, cb=run)
    client.receive_images()

if __name__ == "__main__":
    # init logging
    logging.root.setLevel(logging.DEBUG)
    stream_handler = logging.StreamHandler()
    fmt = logging.Formatter("  [%(process)d|%(levelno)s] %(name)s::%(funcName)s: %(message)s")
    stream_handler.setFormatter(fmt)
    logging.root.addHandler(stream_handler)

    logger.debug("Starting bimz.py")
    main()    