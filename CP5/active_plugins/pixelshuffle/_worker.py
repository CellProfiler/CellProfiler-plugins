"""PixelShuffle worker logic.

This file is never imported by the main CellProfiler process. It is read
as plain source text by `pixelshuffle.py` and handed to Appose, which
executes it inside the subprocess built from the sibling `pixi.toml`
environment. It may freely depend on anything declared there.
"""

import numpy


def pixel_shuffle(pixel_data, seed=None):
    """Randomly permute the pixel values of `pixel_data`, preserving shape."""
    rng = numpy.random.default_rng(seed)
    shuffled = rng.permutation(pixel_data.reshape(-1))
    return shuffled.reshape(pixel_data.shape)
