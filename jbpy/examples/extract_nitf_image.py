import logging

import numpy as np
from PIL import Image

import jbpy
import jbpy.image_data

try:
    from smart_open import open
except ImportError:
    pass


def write_image(array, band_axis, output_filename):
    """Write pixel array using PIL"""

    # Try to coerce the array into someting PIL can write
    if array.shape[band_axis] == 1:
        # Single band
        array = array.squeeze(band_axis)

    if array.shape[band_axis] == 3:
        # assume RGB
        array = np.moveaxis(
            array, band_axis, -1
        )  # PIL needs RGB to be pixel interleaved

    if array.dtype != np.uint8:
        # try to shove the image into uint8
        array = array.astype(np.float32)
        array -= array.min()
        array = ((255.0 * array) / array.max()).astype(np.uint8)

    image = Image.fromarray(array)
    image.save(output_filename)


def main(args=None):
    import argparse
    import pathlib

    parser = argparse.ArgumentParser(description="Extract an image from a JBP file")
    parser.add_argument("input_filename")
    parser.add_argument("index", type=int, help="zero-based image segment index")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--pil",
        type=pathlib.Path,
        help="Coerce image to 8bit and write using PIL.  Format determined by extension.",
    )
    group.add_argument("--npy", type=pathlib.Path, help="Write image as numpy array")
    config = parser.parse_args(args)
    logging.basicConfig(level=logging.DEBUG)

    ntf = jbpy.Jbp()
    with open(config.input_filename, "rb") as file:
        ntf.load(file)

        image_segment = ntf["ImageSegments"][config.index]
        if image_segment["subheader"]["IC"].value not in ("NC", "NM"):
            raise RuntimeError("Only uncompressed image segments are supported")

        array, band_axis = jbpy.image_data.read_uncompressed_image_data(
            image_segment, file
        )

    if config.pil is not None:
        write_image(array, band_axis, config.pil)
    elif config.npy is not None:
        np.save(config.npy, array)


if __name__ == "__main__":
    main()
