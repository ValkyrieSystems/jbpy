"""Functions for handling image segment data"""

import itertools
import math
import os
import typing

import jbpy
import jbpy.core

BLOCK_NOT_RECORDED = 0xFFFFFFFF

_PVTYPE_TO_AP_TYPE_STRING = {"INT": "u", "SI": "i", "R": "f", "C": "c"}


def array_protocol_typestr(pvtype: str, nbpp: int) -> str:
    """Generate a NumPy array interface protocol typestr describing a NITF pixel

    Arguments
    ---------
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


class MaskTable(typing.TypedDict):
    "JBP Image Data Mask Table"

    IMDATOFF: int
    BMRLNTH: int
    TMRLNTH: int
    TPXCDLNTH: int
    TPXCD: bytes | None
    BMRnBNDm: list[list[int]] | None  # indexed[m][n]
    TMRnBNDm: list[list[int]] | None  # indexed[m][n]


def read_mask_table(
    image_segment: jbpy.core.ImageSegment, file: jbpy.core.BinaryFile_R
) -> MaskTable:
    """Read an image segment's mask table

    Arguments
    ---------
    image_segment: ImageSegment
        Which image segment's mask table to read
    file : file-like
        JBP file containing the image_segment

    Returns
    -------
    dictionary containing the mask table values or None if there is no mask table
    """
    subhdr = image_segment["subheader"]
    file.seek(image_segment["Data"].get_offset(), os.SEEK_SET)
    imdatoff = int.from_bytes(file.read(4), "big", signed=False)
    bmrlnth = int.from_bytes(file.read(2), "big", signed=False)
    tmrlnth = int.from_bytes(file.read(2), "big", signed=False)
    tpxcdlnth = int.from_bytes(file.read(2), "big", signed=False)
    if tpxcdlnth > 0:
        tpxcd_size = int(math.ceil(tpxcdlnth / 8))
        tpxcd = file.read(tpxcd_size)
    else:
        tpxcd = None

    num_blocks = subhdr["NBPR"].value * subhdr["NBPC"].value
    num_bands = subhdr.get("XBANDS", subhdr["NBANDS"]).value

    bmrnbndm: list[list[int]] | None = None
    if bmrlnth == 4:
        bmrnbndm = []  # will be indexed [m][n]
        # From JBP: "Increment n prior to m"
        for band in range(num_bands):
            bmrnbndm.append([])
            for _ in range(num_blocks):
                bmrnbndm[band].append(int.from_bytes(file.read(4), "big", signed=False))

    tmrnbndm: list[list[int]] | None = None
    if tmrlnth == 4:
        tmrnbndm = []  # will be indexed [m][n]
        # From JBP: "Increment n prior to m"
        for band in range(num_bands):
            tmrnbndm.append([])
            for _ in range(num_blocks):
                tmrnbndm[band].append(int.from_bytes(file.read(4), "big", signed=False))

    result: MaskTable = {
        "IMDATOFF": imdatoff,
        "BMRLNTH": bmrlnth,
        "TMRLNTH": tmrlnth,
        "TPXCDLNTH": tpxcdlnth,
        "TPXCD": tpxcd,
        "BMRnBNDm": bmrnbndm,
        "TMRnBNDm": tmrnbndm,
    }

    return result


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

    Arguments
    ---------
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

    #: unique index of this block specified as (band, row, col)
    block_index: tuple[int, int, int]

    #: Offset to first byte of the block relative to the start of the file
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


def block_info_uncompressed(
    image_segment: jbpy.core.ImageSegment, file: jbpy.core.BinaryFile_R | None = None
) -> list[BlockInfo]:
    """
    Describe the blocks comprising an uncompressed image segment

    Arguments
    ---------
    image_segment : ImageSegment
        Which image segment to describe
    file : file-like
        JBP file containing the image_segment.  Required if image segment contains Mask Table. (IC field contains "M")

    Returns
    -------
    list of BlockInfo dictionaries
    """
    subhdr = image_segment["subheader"]
    assert subhdr["IC"].value in ("NC", "NM")
    assert (subhdr["PVTYPE"].value, subhdr["NBPP"].value) in IMPLEMENTED_PIXEL_TYPES

    num_image_bands = subhdr.get("XBANDS", subhdr["NBANDS"]).value
    if subhdr["IMODE"].value == "S":
        # Each band is stored as a separate block
        num_bands_in_block = 1
        num_block_bands = num_image_bands
    else:
        num_bands_in_block = num_image_bands
        num_block_bands = 1

    rows_per_block = subhdr["NPPBV"].value or subhdr["NROWS"].value
    cols_per_block = subhdr["NPPBH"].value or subhdr["NCOLS"].value
    expected_blocks_per_col = int(math.ceil(subhdr["NROWS"].value / rows_per_block))
    expected_blocks_per_row = int(math.ceil(subhdr["NCOLS"].value / cols_per_block))

    if expected_blocks_per_col != subhdr["NBPC"].value:
        raise RuntimeError(
            f"Image segment has {subhdr['NBPC'].value} vertical blocks, expected {expected_blocks_per_col}"
        )
    if expected_blocks_per_row != subhdr["NBPR"].value:
        raise RuntimeError(
            f"Image segment has {subhdr['NBPR'].value} horizontal blocks, expected {expected_blocks_per_row}"
        )

    num_fill_rows = (rows_per_block * expected_blocks_per_col) - subhdr["NROWS"].value
    num_fill_cols = (cols_per_block * expected_blocks_per_row) - subhdr["NCOLS"].value

    if num_fill_rows < 0 or num_fill_cols < 0:
        raise RuntimeError("Image segment is missing blocks")

    # Will not work for NBPP == 12
    block_nbytes = (
        num_bands_in_block * rows_per_block * cols_per_block * subhdr["NBPP"].value // 8
    )

    mask_table = None
    if "M" in subhdr["IC"].value:
        assert file is not None
        mask_table = read_mask_table(image_segment, file)

    blocks = []
    image_offset = image_segment["Data"].get_offset()
    for block_counter, block_index in enumerate(
        itertools.product(
            range(num_block_bands),
            range(subhdr["NBPC"].value),
            range(subhdr["NBPR"].value),
        )
    ):
        block_band, block_row, block_col = block_index

        start_row = block_row * rows_per_block
        start_col = block_col * cols_per_block

        # how much fill is in this block
        fill_rows = num_fill_rows if block_row == subhdr["NBPC"].value - 1 else 0
        fill_cols = num_fill_cols if block_col == subhdr["NBPR"].value - 1 else 0
        image_slice_rows = slice(start_row, start_row + rows_per_block - fill_rows)
        image_slice_cols = slice(start_col, start_col + cols_per_block - fill_cols)
        block_slice_rows = slice(0, rows_per_block - fill_rows)
        block_slice_cols = slice(0, cols_per_block - fill_cols)

        image_slicing: Slice3DType
        block_slicing: Slice3DType
        if subhdr["IMODE"].value == "P":
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
        elif subhdr["IMODE"].value == "B":
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
        elif subhdr["IMODE"].value == "R":
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
        elif subhdr["IMODE"].value == "S":
            shape = (1, rows_per_block, cols_per_block)
            image_slicing = (
                block_band,  # single band
                image_slice_rows,
                image_slice_cols,
            )
            block_slicing = (
                block_band,  # single band
                block_slice_rows,
                block_slice_cols,
            )
            band_axis = 0

        # Nominal description for unmasked/unpadded data, "NC"
        info: BlockInfo = {
            "block_index": block_index,  # block_band, block_row, block_col
            "offset": image_offset + block_nbytes * block_counter,
            "nbytes": block_nbytes,
            "shape": shape,
            "typestr": array_protocol_typestr(
                subhdr["PVTYPE"].value, subhdr["NBPP"].value
            ),
            "image_slicing": image_slicing,
            "block_slicing": block_slicing,
            "fill_rows": fill_rows,
            "fill_cols": fill_cols,
            "has_pad": False,
            "pad_value": None,
            "band_axis": band_axis,
        }

        # Update description for masked data.  "NM"
        if mask_table is not None:
            # mask tables are inserted immediately before the pixel data
            assert info["offset"] is not None
            info["offset"] += mask_table["IMDATOFF"]

            n = block_row * subhdr["NBPR"].value + block_col
            m = block_band
            if mask_table["TPXCD"] is not None:
                info["pad_value"] = mask_table["TPXCD"]
            if mask_table["BMRnBNDm"] is not None:
                if (
                    mask_table["BMRnBNDm"][m][n] == BLOCK_NOT_RECORDED
                ):  # block is omitted from file
                    info["offset"] = None
                    info["nbytes"] = 0
                else:
                    info["offset"] = (
                        image_offset
                        + mask_table["IMDATOFF"]
                        + mask_table["BMRnBNDm"][m][n]
                    )
            if mask_table["TMRnBNDm"] is not None:
                info["has_pad"] = mask_table["TMRnBNDm"][m][n] != BLOCK_NOT_RECORDED

        blocks.append(info)

    return blocks
