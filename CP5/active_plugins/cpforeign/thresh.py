import logging
import numpy as np
import skimage as ski
import scipy as sp

from server import ForeignToolClient

logger = logging.getLogger(__name__)


def run(image_data, image_header):
    im = (image_data * 255).astype(np.uint8)

    markers = np.zeros_like(im, dtype=np.uint8)
    IDK = 0
    BG = 1
    FG = 2
    markers[im < 30] = BG
    markers[im > 50] = FG
    # rest = IDK

    elevation_map = ski.filters.sobel(im)
    segmentation = ski.segmentation.watershed(elevation_map, markers)
    segmentation = sp.ndimage.binary_fill_holes(segmentation - 1)

    labels, _ = sp.ndimage.label(segmentation)

    # remove small objects
    sizes = np.bincount(labels.ravel())
    mask_sizes = sizes > 20
    mask_sizes[0] = 0
    segmentation = mask_sizes[labels]

    labels, _ = sp.ndimage.label(segmentation)

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

    logger.debug("Starting thresh.py")
    main()