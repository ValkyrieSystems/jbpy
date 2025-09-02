import os
import pathlib

import numpy as np
import pytest

import jbpy
import jbpy.image_data


@pytest.mark.parametrize(
    "pvtype,nbpp,expected_typestr",
    [
        ("INT", 8, ">u1"),
        ("INT", 16, ">u2"),
        ("INT", 32, ">u4"),
        ("INT", 64, ">u8"),
        ("SI", 8, ">i1"),
        ("SI", 16, ">i2"),
        ("SI", 32, ">i4"),
        ("SI", 64, ">i8"),
        ("R", 32, ">f4"),
        ("R", 64, ">f8"),
        ("C", 64, ">c8"),
    ],
)
def test_array_protocol_typestr(pvtype, nbpp, expected_typestr):
    typestr = jbpy.image_data.array_protocol_typestr(pvtype, nbpp)
    assert typestr == expected_typestr
    dtype = np.dtype(typestr)
    assert dtype.itemsize == nbpp // 8


def find_jitc_ql_img_pos_04():
    # See https://jitc.fhu.disa.mil/projects/nitf/testdata.aspx
    root_dir = pathlib.Path(os.environ.get("JBPY_JITC_QUICKLOOK_DIR"))
    candidates = list(root_dir.glob("**/NITF_IMG_POS_04.ntf"))
    assert len(candidates) == 1
    return candidates[0]


@pytest.mark.skipif(
    "JBPY_JITC_QUICKLOOK_DIR" not in os.environ,
    reason="requires JITC Quick-Look data",
)
def test_read_mask_table():
    filename = find_jitc_ql_img_pos_04()
    jbp = jbpy.Jbp()
    with filename.open("rb") as file:
        jbp.load(file)

        subheader = jbp["ImageSegments"][1]["subheader"]
        assert subheader["IC"].value == "NM"
        assert subheader["NBPC"].value > 1
        assert subheader["NBPR"].value > 1
        assert subheader["NBANDS"].value == 1

        mask_table = jbpy.image_data.read_mask_table(jbp["ImageSegments"][1], file)
        assert len(mask_table["BMRnBNDm"]) == 1
        assert (
            len(mask_table["BMRnBNDm"][0])
            == subheader["NBPC"].value * subheader["NBPR"].value
        )
        block_size = (
            subheader["NPPBV"].value
            * subheader["NPPBV"].value
            * subheader["NBPP"].value
            // 8
        )
        included_offsets = [
            offset
            for offset in mask_table["BMRnBNDm"][0]
            if offset != jbpy.image_data.BLOCK_NOT_RECORDED
        ]

        assert len(included_offsets) < len(
            mask_table["BMRnBNDm"][0]
        )  # make sure this dataset omits a block

        assert (
            jbp["FileHeader"]["LI002"].value
            == block_size * len(included_offsets) + mask_table["IMDATOFF"]
        )
        assert np.all(np.diff(included_offsets) % block_size) == 0


@pytest.mark.skipif(
    "JBPY_JITC_QUICKLOOK_DIR" not in os.environ,
    reason="requires JITC Quick-Look data",
)
def test_array_description():
    filename = find_jitc_ql_img_pos_04()

    jbp = jbpy.Jbp()
    with filename.open("rb") as file:
        jbp.load(file)

    subheader = jbp["ImageSegments"][1]["subheader"]
    assert subheader["NBANDS"].value == 1
    assert subheader["IMODE"].value == "B"

    shape, band_axis, typestr = jbpy.image_data.image_array_description(
        jbp["ImageSegments"][1]
    )
    assert band_axis == 0
    assert shape == (1, subheader["NROWS"].value, subheader["NCOLS"].value)
    assert np.dtype(typestr).itemsize == subheader["NBPP"].value // 8


@pytest.mark.skipif(
    "JBPY_JITC_QUICKLOOK_DIR" not in os.environ,
    reason="requires JITC Quick-Look data",
)
def test_block_info_uncompressed():
    filename = find_jitc_ql_img_pos_04()

    jbp = jbpy.Jbp()
    with filename.open("rb") as file:
        jbp.load(file)

        subheader = jbp["ImageSegments"][1]["subheader"]

        assert subheader["NROWS"].value == 1536
        assert subheader["NCOLS"].value == 1536

        assert subheader["NBPC"].value == 3
        assert subheader["NBPR"].value == 3
        assert subheader["IC"].value == "NM"
        assert subheader["IMODE"].value == "B"
        assert subheader["NBANDS"].value == 1

        # modify NROWS/NCOLS to force fill
        row_fill = 100
        col_fill = 200
        subheader["NROWS"].value -= row_fill
        subheader["NCOLS"].value -= col_fill

        mask_table = jbpy.image_data.read_mask_table(jbp["ImageSegments"][1], file)

        block_infos = jbpy.image_data.block_info_uncompressed(
            jbp["ImageSegments"][1], file
        )
        assert len(block_infos) == (subheader["NBPC"].value * subheader["NBPR"].value)

        assert block_infos[0]["block_index"] == (0, 0, 0)
        assert (
            block_infos[0]["offset"]
            == jbp["ImageSegments"][1]["Data"].get_offset() + mask_table["IMDATOFF"]
        )
        assert (
            block_infos[0]["nbytes"]
            == subheader["NPPBH"].value
            * subheader["NPPBV"].value
            * subheader["NBPP"].value
            // 8
        )
        assert block_infos[0]["shape"] == (
            1,
            subheader["NPPBH"].value,
            subheader["NPPBV"].value,
        )
        assert block_infos[0]["band_axis"] == 0
        assert (
            np.dtype(block_infos[0]["typestr"]).itemsize == subheader["NBPP"].value // 8
        )

        assert len(block_infos[0]["image_slicing"]) == 3
        assert block_infos[0]["image_slicing"][0].start is None
        assert block_infos[0]["image_slicing"][0].stop is None
        assert block_infos[0]["image_slicing"][1].start == 0
        assert block_infos[0]["image_slicing"][1].stop == subheader["NPPBV"].value
        assert block_infos[0]["image_slicing"][2].start == 0
        assert block_infos[0]["image_slicing"][2].stop == subheader["NPPBH"].value

        assert len(block_infos[0]["block_slicing"]) == 3
        assert block_infos[0]["block_slicing"][0].start is None
        assert block_infos[0]["block_slicing"][0].stop is None
        assert block_infos[0]["block_slicing"][1].start == 0
        assert block_infos[0]["block_slicing"][1].stop == subheader["NPPBV"].value
        assert block_infos[0]["block_slicing"][2].start == 0
        assert block_infos[0]["block_slicing"][2].stop == subheader["NPPBH"].value

        assert block_infos[0]["fill_rows"] == 0
        assert block_infos[0]["fill_cols"] == 0

        assert block_infos[0]["has_pad"] == (mask_table["TMRLNTH"] == 4)
        assert block_infos[0]["pad_value"] == mask_table["TPXCD"]

        assert block_infos[-1]["image_slicing"][0].start is None
        assert block_infos[-1]["image_slicing"][0].stop is None
        assert (
            block_infos[-1]["image_slicing"][1].start
            == subheader["NROWS"].value - subheader["NPPBV"].value + row_fill
        )
        assert block_infos[-1]["image_slicing"][1].stop == subheader["NROWS"].value
        assert (
            block_infos[-1]["image_slicing"][2].start
            == subheader["NCOLS"].value - subheader["NPPBH"].value + col_fill
        )
        assert block_infos[-1]["image_slicing"][2].stop == subheader["NCOLS"].value
        assert block_infos[-1]["block_slicing"][0].start is None
        assert block_infos[-1]["block_slicing"][0].stop is None
        assert block_infos[-1]["block_slicing"][1].start == 0
        assert (
            block_infos[-1]["block_slicing"][1].stop
            == subheader["NPPBV"].value - row_fill
        )
        assert block_infos[-1]["block_slicing"][2].start == 0
        assert (
            block_infos[-1]["block_slicing"][2].stop
            == subheader["NPPBH"].value - col_fill
        )
        assert block_infos[-1]["fill_rows"] == row_fill
        assert block_infos[-1]["fill_cols"] == col_fill
