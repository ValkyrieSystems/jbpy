"""Functions for handling image segment data"""

from __future__ import annotations  # needed for python < 3.14

import copy
import itertools
import logging
import math
import os
import typing

import jbpy.core

try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

BLOCK_NOT_RECORDED = 0xFFFFFFFF

_PVTYPE_TO_AP_TYPE_STRING = {"INT": "u", "SI": "i", "R": "f", "C": "c"}


def array_protocol_typestr(pvtype: str, nbpp: int) -> str:
    """Generate a NumPy array interface protocol typestr describing a NITF pixel

    Parameters
    ----------
    pvtype : str
        Image subheader Pixel Value Type (PVTYPE)
    nbpp : int
        Image subheader Number of Bits Per Pixel Per Band (NBPP)

    Notes
    -----
    The resulting typestr is sutable for storing the pixel value.
    Additional transforms of the pixel values may be necessary to account
    for PJUST and ABPP.
    """
    assert nbpp % 8 == 0  # 12bit not implemented
    dtype_str = ">"
    dtype_str += _PVTYPE_TO_AP_TYPE_STRING[pvtype]
    dtype_str += str(int(nbpp // 8))
    return dtype_str


class BinaryUnsignedInteger(jbpy.core.PythonConverter):
    """convert to/from a binary integer"""

    def to_bytes_impl(self, decoded_value: int, size: int) -> bytes:
        decoded_value = int(decoded_value)
        return decoded_value.to_bytes(size, byteorder="big", signed=False)

    def from_bytes_impl(self, encoded_value: bytes) -> int:
        return int.from_bytes(encoded_value, byteorder="big", signed=False)


# MaskTable is defined here rather than in jbpy.core because jbpy.core's existing callback
# support makes it difficult to keep MaskTable updated when NBPR, NBPC, NBANDS, and XBANDS change.
# As a result it doesn't behave quite like the other Groups.
class MaskTable(jbpy.core.Group):
    """JBP Image Data Mask Table

    Parameters
    ----------
    name : str
        Name to give this group
    image_subheader : jbpy.core.ImageSubheader
        Subheader for the image segment containing the mask table

    Notes
    -----
    image_subheader must not change after initializing this class.
    """

    def __init__(self, name: str, image_subheader: jbpy.core.ImageSubheader):
        super().__init__(name)
        self._num_blocks = image_subheader["NBPC"].value * image_subheader["NBPR"].value

        if image_subheader["IMODE"].value == "S":
            # Each band is stored as a separate block
            self._num_bands = image_subheader.get(
                "XBANDS", image_subheader["NBANDS"]
            ).value
        else:
            self._num_bands = 1

        self._append(
            jbpy.core.Field(
                "IMDATOFF",
                "Blocked Image Data Offset",
                4,
                converter=BinaryUnsignedInteger(),
                default=0,
            )
        )
        self._append(
            jbpy.core.Field(
                "BMRLNTH",
                "Block Mask Record Length",
                2,
                decoded_range=jbpy.core.Enum([0, 4]),
                converter=BinaryUnsignedInteger(),
                default=0,
                setter_callback=self._handle_bmrlnth,
            )
        )
        self._append(
            jbpy.core.Field(
                "TMRLNTH",
                "Pad Pixel Mask Record Length",
                2,
                decoded_range=jbpy.core.Enum([0, 4]),
                converter=BinaryUnsignedInteger(),
                default=0,
                setter_callback=self._handle_tmrlnth,
            )
        )
        self._append(
            jbpy.core.Field(
                "TPXCDLNTH",
                "Pad Output Pixel Code Length",
                2,
                converter=BinaryUnsignedInteger(),
                default=0,
                setter_callback=self._handle_tpxcdlnth,
            )
        )

    def _handle_bmrlnth(self, field):
        self._remove_all("BMR\\d+BND\\d+")
        if field.value == 0:
            return

        after = self["TPXCDLNTH"]
        if "TPXCD" in self:
            after = self["TPXCD"]

        for band_idx in range(self._num_bands):
            for block_idx in range(self._num_blocks):
                name = self.bmr_name(block_idx, band_idx)
                after = self._insert_after(
                    after,
                    jbpy.core.Field(
                        name,
                        f"Block {block_idx}, Band {band_idx} Offset",
                        4,
                        converter=BinaryUnsignedInteger(),
                        default=0,
                    ),
                )

    def _handle_tmrlnth(self, field):
        self._remove_all("TMR\\d+BND\\d+")
        if field.value == 0:
            return

        after = self["TPXCDLNTH"]
        if "TPXCD" in self:
            after = self["TPXCD"]

        for bmr_field in self.find_all("BMR\\d+BND\\d+"):
            if bmr_field.get_offset() > after.get_offset():
                after = bmr_field

        for band_idx in range(self._num_bands):
            for block_idx in range(self._num_blocks):
                name = self.tmr_name(block_idx, band_idx)
                after = self._insert_after(
                    after,
                    jbpy.core.Field(
                        name,
                        f"Pad Pixel {block_idx}, Band {band_idx}",
                        4,
                        converter=BinaryUnsignedInteger(),
                        default=0,
                    ),
                )

    def _handle_tpxcdlnth(self, field):
        self._remove_all("TPXCD")
        tpxcd_length = int(math.ceil(field.value / 8))
        if tpxcd_length > 0:
            self._insert_after(
                field,
                jbpy.core.Field(
                    "TPXCD",
                    "Pad Output Pixel Code",
                    tpxcd_length,
                    converter=jbpy.core.Bytes(),
                    default=b"\x00" * tpxcd_length,
                ),
            )

    @staticmethod
    def bmr_name(block_index: int, band_index: int) -> str:
        """Generate the expected name for BMRnBNDm given indices

        Parameters
        ----------
        block_index : int
            Linear index of the block (zero-based).  "n"
        band_index : int
            Index of the band (zero-based).  "m"

        Returns
        -------
        str
            Field name
        """
        return f"BMR{block_index:08d}BND{band_index:05d}"

    @staticmethod
    def tmr_name(block_index: int, band_index: int) -> str:
        """Generate the expected name for TMRnBNDm given indices

        Parameters
        ----------
        block_index : int
            Linear index of the block (one-based).  "n"
        band_index : int
            Index of the band (one-based).  "m"

        Returns
        -------
        str
            Field name
        """
        return f"TMR{block_index:08d}BND{band_index:05d}"


def read_mask_table(
    image_segment: jbpy.core.ImageSegment, file: jbpy.core.BinaryFile_R
) -> MaskTable:
    """Read an image segment's mask table

    Parameters
    ----------
    image_segment : ImageSegment
        Which image segment's mask table to read
    file : file-like
        JBP file containing the image_segment

    Returns
    -------
    dictionary containing the mask table values or None if there is no mask table
    """
    assert "M" in image_segment["subheader"]["IC"].value
    file.seek(image_segment["Data"].get_offset(), os.SEEK_SET)
    mt = MaskTable("MaskTable", image_segment["subheader"])
    mt.load(file)
    return mt


IMPLEMENTED_PIXEL_TYPES = [  # (PVTYPE, NBPP)
    ("INT", 8),
    # ('INT', 12),  # 12-bit not implemented
    ("INT", 16),
    ("INT", 32),
    ("INT", 64),
    ("SI", 8),
    # ('SI', 12),  # 12-bit not implemented
    ("SI", 16),
    ("SI", 32),
    ("SI", 64),
    ("R", 32),
    ("R", 64),
    ("C", 64),
]


def image_array_description(
    image_segment: jbpy.core.ImageSegment,
) -> tuple[tuple[int, int, int], int, str]:
    """Shape of image described by the image segment

    Always describes a 3D shape with one axis being the bands.
    Axis containing the bands is determined by the IMODE field.

    Parameters
    ----------
    image_segment : jbpy.core.ImageSegment
        The image segment to describe

    Returns
    -------
    shape : tuple
        Shape of the full image
    band_axis : int
        Which axis contains the bands.  Other two axes will be rows and cols, respectively.
    typestr : str
        Array interface protocol typestr describing the pixel type
    """
    subhdr = image_segment["subheader"]
    num_bands = subhdr.get("XBANDS", subhdr["NBANDS"]).value
    nrows = subhdr["NROWS"].value
    ncols = subhdr["NCOLS"].value
    imode = subhdr["IMODE"].value
    pvtype = subhdr["PVTYPE"].value
    nbpp = subhdr["NBPP"].value

    if imode == "B":
        shape = (num_bands, nrows, ncols)
        band_axis = 0
    elif imode == "P":
        shape = (nrows, ncols, num_bands)
        band_axis = 2
    elif imode == "R":
        shape = (nrows, num_bands, ncols)
        band_axis = 1
    elif imode == "S":
        shape = (num_bands, nrows, ncols)
        band_axis = 0

    typestr = array_protocol_typestr(pvtype, nbpp)

    return shape, band_axis, typestr


Slice3DType = tuple[slice | int, slice | int, slice | int]


class BlockInfo(typing.TypedDict):
    """Information describing a single image data block"""

    #: band index of this block.  Zero unless IMODE == S
    block_band_index: int

    #: row index of this block
    block_row_index: int

    #: col index of this block
    block_col_index: int

    #: Offset to first byte of the block relative to the start of the image data
    offset: int | None

    #: Size of the block in bytes (including fill pixels)
    nbytes: int

    #: Shape of the block
    shape: tuple[int, int, int]

    #: Which axis of the block's shape contains the bands
    band_axis: int

    #: Array interface protocol typestr for the block's pixels
    typestr: str

    #: 3D slice of full image describing this blocks' non-fill pixels
    image_slicing: Slice3DType

    #: 3D slice of this block describing the non-fill pixels
    block_slicing: Slice3DType

    #: How many rows of fill are contained in this block
    fill_rows: int

    #: How many columns of fill are contained in this block
    fill_cols: int

    #: Does this block contain pad pixels
    has_pad: bool

    #: pixel bit pattern identifiying pad pixels
    pad_value: bytes | None


def nominal_block_info(image_subheader: jbpy.core.ImageSubheader) -> list[BlockInfo]:
    """Create a list of block information assuming an image is uncompressed and unmasked (IC=NC)

    Parameters
    ----------
    image_subheader : jbpy.core.ImageSubheader
        Subheader of the image to describe

    Returns
    -------
    list of BlockInfo dictionaries in the order they would appear in the data stream
    """

    assert (
        image_subheader["PVTYPE"].value,
        image_subheader["NBPP"].value,
    ) in IMPLEMENTED_PIXEL_TYPES

    num_image_bands = image_subheader.get("XBANDS", image_subheader["NBANDS"]).value
    if image_subheader["IMODE"].value == "S":
        # Each band is stored as a separate block
        num_bands_in_block = 1
        num_block_bands = num_image_bands
    else:
        num_bands_in_block = num_image_bands
        num_block_bands = 1

    rows_per_block = image_subheader["NPPBV"].value or image_subheader["NROWS"].value
    cols_per_block = image_subheader["NPPBH"].value or image_subheader["NCOLS"].value
    expected_blocks_per_col = int(
        math.ceil(image_subheader["NROWS"].value / rows_per_block)
    )
    expected_blocks_per_row = int(
        math.ceil(image_subheader["NCOLS"].value / cols_per_block)
    )

    if expected_blocks_per_col != image_subheader["NBPC"].value:
        raise RuntimeError(
            f"Image segment has {image_subheader['NBPC'].value} vertical blocks, expected {expected_blocks_per_col}"
        )
    if expected_blocks_per_row != image_subheader["NBPR"].value:
        raise RuntimeError(
            f"Image segment has {image_subheader['NBPR'].value} horizontal blocks, expected {expected_blocks_per_row}"
        )

    num_fill_rows = (rows_per_block * expected_blocks_per_col) - image_subheader[
        "NROWS"
    ].value
    num_fill_cols = (cols_per_block * expected_blocks_per_row) - image_subheader[
        "NCOLS"
    ].value

    if num_fill_rows < 0 or num_fill_cols < 0:
        raise RuntimeError("Image segment is missing blocks")

    # Will not work for NBPP == 12
    block_nbytes = (
        num_bands_in_block
        * rows_per_block
        * cols_per_block
        * image_subheader["NBPP"].value
        // 8
    )

    blocks = []
    for block_counter, block_indices in enumerate(
        itertools.product(
            range(num_block_bands),
            range(image_subheader["NBPC"].value),
            range(image_subheader["NBPR"].value),
        )
    ):
        block_band_index, block_row_index, block_col_index = block_indices
        start_row = block_row_index * rows_per_block
        start_col = block_col_index * cols_per_block

        # how much fill is in this block
        fill_rows = (
            num_fill_rows if block_row_index == image_subheader["NBPC"].value - 1 else 0
        )
        fill_cols = (
            num_fill_cols if block_col_index == image_subheader["NBPR"].value - 1 else 0
        )
        image_slice_rows = slice(start_row, start_row + rows_per_block - fill_rows)
        image_slice_cols = slice(start_col, start_col + cols_per_block - fill_cols)
        block_slice_rows = slice(0, rows_per_block - fill_rows)
        block_slice_cols = slice(0, cols_per_block - fill_cols)

        image_slicing: Slice3DType
        block_slicing: Slice3DType
        if image_subheader["IMODE"].value == "P":
            shape = (rows_per_block, cols_per_block, num_image_bands)
            image_slicing = (
                image_slice_rows,
                image_slice_cols,
                slice(None, None),  # all bands
            )
            block_slicing = (
                block_slice_rows,
                block_slice_cols,
                slice(None, None),  # all bands
            )
            band_axis = 2
        elif image_subheader["IMODE"].value == "B":
            shape = (num_image_bands, rows_per_block, cols_per_block)
            image_slicing = (
                slice(None, None),  # all bands
                image_slice_rows,
                image_slice_cols,
            )
            block_slicing = (
                slice(None, None),  # all bands
                block_slice_rows,
                block_slice_cols,
            )
            band_axis = 0
        elif image_subheader["IMODE"].value == "R":
            shape = (rows_per_block, num_image_bands, cols_per_block)
            image_slicing = (
                image_slice_rows,
                slice(None, None),  # all bands
                image_slice_cols,
            )
            block_slicing = (
                block_slice_rows,
                slice(None, None),  # all bands
                block_slice_cols,
            )
            band_axis = 1
        elif image_subheader["IMODE"].value == "S":
            shape = (1, rows_per_block, cols_per_block)
            image_slicing = (
                block_band_index,  # single band
                image_slice_rows,
                image_slice_cols,
            )
            block_slicing = (
                0,  # each block contains only a single band
                block_slice_rows,
                block_slice_cols,
            )
            band_axis = 0

        # Nominal description for unmasked/unpadded data, "NC"
        info: BlockInfo = {
            "block_band_index": block_band_index,
            "block_row_index": block_row_index,
            "block_col_index": block_col_index,
            "offset": block_nbytes * block_counter,
            "nbytes": block_nbytes,
            "shape": shape,
            "typestr": array_protocol_typestr(
                image_subheader["PVTYPE"].value, image_subheader["NBPP"].value
            ),
            "image_slicing": image_slicing,
            "block_slicing": block_slicing,
            "fill_rows": fill_rows,
            "fill_cols": fill_cols,
            "has_pad": False,
            "pad_value": None,
            "band_axis": band_axis,
        }
        blocks.append(info)

    blocks = sorted(blocks, key=lambda x: x["offset"] or 0)

    return blocks


def apply_mask_table_to_block_info(
    image_subheader: jbpy.core.ImageSubheader,
    block_info: list[BlockInfo],
    mask_table: MaskTable,
) -> list[BlockInfo]:
    """Return a copy of a block_info list with information from a mask table applied

    Parameters
    ----------
    image_subheader : jbpy.core.ImageSubheader
        Subheader of the image to describe
    block_info : list of BlockInfo
        Input BlockInfo dictionaries
    mask_table : MaskTable
        Mask Table from the image segment

    Returns
    -------
    list of BlockInfo dictionaries
    """
    assert "M" in image_subheader["IC"].value

    block_info = copy.deepcopy(block_info)

    # Update description for masked data.  "NM"
    for info in block_info:
        # mask tables are inserted immediately before the pixel data
        assert info["offset"] is not None
        info["offset"] += mask_table["IMDATOFF"].value

        n = (
            info["block_row_index"] * image_subheader["NBPR"].value
            + info["block_col_index"]
        )
        m = info["block_band_index"]
        if "TPXCD" in mask_table:
            info["pad_value"] = mask_table["TPXCD"].value

        bmr_name = mask_table.bmr_name(n, m)
        if bmr_name in mask_table:
            if (
                mask_table[bmr_name].value == BLOCK_NOT_RECORDED
            ):  # block is omitted from file
                info["offset"] = None
                info["nbytes"] = 0
            else:
                info["offset"] = (
                    +mask_table["IMDATOFF"].value + mask_table[bmr_name].value
                )
        tmr_name = mask_table.tmr_name(n, m)
        if tmr_name in mask_table:
            info["has_pad"] = mask_table[tmr_name].value != BLOCK_NOT_RECORDED

    return block_info


def _fetch_uncompressed_block(
    block_info: BlockInfo, file: jbpy.core.BinaryFile_R, image_data_offset: int
) -> np.ndarray:
    """Read a single uncompressed image block from a file"""

    if not HAS_NUMPY:
        raise ModuleNotFoundError(
            "numpy is required for reading blocked data, but is not installed."
        )

    logging.debug(
        f"fetching block {block_info['block_band_index'], block_info['block_row_index'], block_info['block_col_index']}"
    )

    dtype = np.dtype(block_info["typestr"])
    if block_info["offset"] is None:
        logging.debug("block not present in file, zero filling")
        return np.broadcast_to(dtype.type(0), block_info["shape"])
    offset_to_block = image_data_offset + block_info["offset"]
    array: np.ndarray
    try:
        array = np.memmap(
            file,
            mode="readonly",
            dtype=dtype,
            offset=offset_to_block,
            shape=block_info["shape"],
        )  # type: ignore
    except Exception:
        logging.debug("memmap failed. Using seek and read")
        file.seek(offset_to_block, os.SEEK_SET)
        array = np.frombuffer(
            file.read(block_info["nbytes"]),
            dtype=dtype,
            count=np.prod(block_info["shape"]),
        ).reshape(block_info["shape"])

    if block_info["has_pad"]:
        # TODO use numpy masked arrays
        logging.warning("Unhandled pad pixels")
    return array


def read_uncompressed_image_data(
    jbp: jbpy.core.Jbp,
    image_segment_index: int,
    file: jbpy.core.BinaryFile_R,
) -> tuple[np.ndarray, int]:
    """
    Read an image data stream and mosaic into a contiguous raster

    Parameters
    ----------
    jbp : Jbp
        Jbp object
    image_segment_index : int
        index of the image segment to read
    file : file-like
        JBP file open for binary reading

    Returns
    -------
    image : ndarray
        3D array with one axis being the bands and the remaining two rows and columns respectively
    band_axis : int
        which axis of the ndarray contains the band(s)
    """
    if not HAS_NUMPY:
        raise ModuleNotFoundError(
            "numpy is required for writing an ndarray, but is not installed."
        )

    image_segment = jbp["ImageSegments"][image_segment_index]
    subhdr = image_segment["subheader"]
    if subhdr["IC"].value not in ("NC", "NM"):
        raise NotImplementedError("Compression not supported")

    blocks = nominal_block_info(subhdr)
    if "M" in subhdr["IC"].value:
        mask_table = read_mask_table(image_segment, file)
        blocks = apply_mask_table_to_block_info(subhdr, blocks, mask_table)

    shape, band_axis, dtype_string = image_array_description(image_segment)
    array = np.empty(shape, dtype=dtype_string)

    for info in blocks:
        block_array = _fetch_uncompressed_block(
            info, file, image_segment["Data"].get_offset()
        )
        array[info["image_slicing"]] = block_array[info["block_slicing"]]

    return array, band_axis


COMPRESSION_READERS = {
    "NC": read_uncompressed_image_data,
    "NM": read_uncompressed_image_data,
}

# TODO compression reader entrypoint?


def read_image_data(
    jbp: jbpy.core.Jbp,
    image_segment_index: int,
    file: jbpy.core.BinaryFile_R,
) -> tuple[np.ndarray, int]:
    """
    Read the pixel data from an image segment

    Parameters
    ----------
    jbp : Jbp
        Jbp object
    image_segment_index : int
        index of the image segment to read
    file : file-like
        JBP file open for binary reading

    Returns
    -------
    image : ndarray
        3D array with one axis being the bands and the remaining two rows and columns respectively
    band_axis : int
        which axis of the ndarray contains the band(s)
    """

    image_segment = jbp["ImageSegments"][image_segment_index]
    compression = image_segment["subheader"]["IC"].value
    handler = COMPRESSION_READERS.get(compression)

    if handler is not None:
        return handler(jbp, image_segment_index, file)

    raise NotImplementedError(f"Unhandled compression {compression}")


def write_uncompressed_image_data(
    jbp: jbpy.core.Jbp,
    image_segment_index: int,
    file: jbpy.core.BinaryFile_RW,
    array: np.ndarray,
    mask_table: MaskTable | None = None,
) -> None:
    """
    Write NC or NM image data

    Parameters
    ----------
    jbp : Jbp
        Jbp object
    image_segment_index : int
        index of the image segment to write
    file : file-like
        JBP file open for binary reading and writing
    array : ndarray
        image to write
    mask_table : MaskTable or None, optional
        The mask table to use when compression is "NM"
    """

    if not HAS_NUMPY:
        raise ModuleNotFoundError(
            "numpy is required for writing an ndarray, but is not installed."
        )
    image_segment = jbp["ImageSegments"][image_segment_index]

    if image_segment["subheader"]["IC"].value not in ("NC", "NM"):
        raise NotImplementedError("Compression not supported")

    if image_segment["subheader"]["IC"].value == "NM" and mask_table is None:
        raise RuntimeError("mask_table required when image compression is 'NM'")

    expected_shape, expected_band_axis, expected_typestr = image_array_description(
        image_segment
    )

    if array.ndim == 2 and image_segment["subheader"]["NBANDS"].value == 1:
        # need array to always be 3D with a band axis
        array = np.expand_dims(array, expected_band_axis)

    if array.shape != expected_shape:
        raise RuntimeError(f"array has shape {array.shape}, expected {expected_shape}")

    if array.dtype.newbyteorder("=") != np.dtype(expected_typestr).newbyteorder("="):
        # only allowed to differ by byte-order
        raise RuntimeError(
            f"array has incompatible type {array.dtype.str}, expected {expected_typestr}"
        )

    file.seek(image_segment["Data"].get_offset(), os.SEEK_SET)

    blocks = nominal_block_info(image_segment["subheader"])
    if mask_table is not None:
        blocks = apply_mask_table_to_block_info(
            image_segment["subheader"], blocks, mask_table
        )
        blocks = [
            block for block in blocks if block["offset"] is not None
        ]  # masked blocks aren't written

    # Verify LInnn is set correctly
    block_size = np.prod(blocks[-1]["shape"]) * np.dtype(blocks[-1]["typestr"]).itemsize
    data_size = blocks[-1]["offset"] + block_size  # type: ignore
    length_name = f"LI{image_segment_index + 1:03d}"
    li = jbp["FileHeader"][length_name].value
    if data_size != li:
        raise RuntimeError(
            f"Mismatch between {length_name}: {li} and data size to be written: {data_size}"
        )

    if mask_table is not None:
        mask_table.dump(file)

    for block in blocks:
        if block["fill_rows"] or block["fill_cols"]:
            tile = np.zeros(block["shape"], dtype=block["typestr"])
            tile[block["block_slicing"]] = array[block["image_slicing"]]
        else:
            tile = array[block["image_slicing"]]

        tile = tile.astype(expected_typestr, copy=False)  # handle byte-swapping
        tile = np.ascontiguousarray(tile)  # JBP is row-major
        tile.tofile(file)  # type: ignore
