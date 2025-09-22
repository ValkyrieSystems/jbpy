import logging
import os

import numpy as np
import numpy.typing as npt
from PIL import Image

import jbpy
import jbpy.image_data

try:
    from smart_open import open
except ImportError:
    pass


def _fetch_block_uncompressed(
    info: jbpy.image_data.BlockInfo,
    file: jbpy.core.BinaryFile_R,
    image_data_offset,
):
    logging.debug(
        f"fetching block {info['block_band_index'], info['block_row_index'], info['block_col_index']}"
    )

    dtype = np.dtype(info["typestr"])
    if info["offset"] is None:
        logging.debug("block not present in file, zero filling")
        return np.broadcast_to(dtype.type(0), info["shape"])
    offset_to_block = image_data_offset + info["offset"]
    array: npt.NDArray
    try:
        array = np.memmap(
            file,
            mode="readonly",
            dtype=dtype,
            offset=offset_to_block,
            shape=info["shape"],
        )  # type: ignore
    except Exception:
        logging.debug("memmap failed. Using seek and read")
        file.seek(offset_to_block, os.SEEK_SET)
        array = np.frombuffer(
            file.read(info["nbytes"]),
            dtype=dtype,
            count=np.prod(info["shape"]),
        ).reshape(info["shape"])

    if info["has_pad"]:
        # TODO use numpy masked arrays
        logging.warning("Unhandled pad pixels")
    return array


def read_entire_image_uncompressed(
    image_segment: jbpy.core.ImageSegment,
    file: jbpy.core.BinaryFile_R,
):
    subhdr = image_segment["subheader"]
    assert subhdr["IC"].value in ("NC", "NM")

    blocks = jbpy.image_data.block_info_uncompressed(image_segment, file)
    logging.debug(f"reading {len(blocks)} blocks")

    shape, band_axis, dtype_string = jbpy.image_data.image_array_description(
        image_segment
    )
    array = np.empty(shape, dtype=dtype_string)

    for info in blocks:
        block_array = _fetch_block_uncompressed(
            info, file, image_segment["Data"].get_offset()
        )
        array[info["image_slicing"]] = block_array[info["block_slicing"]]

    return array, band_axis


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

        array, band_axis = read_entire_image_uncompressed(image_segment, file)

    if config.pil is not None:
        write_image(array, band_axis, config.pil)
    elif config.npy is not None:
        np.save(config.npy, array)


if __name__ == "__main__":
    main()
