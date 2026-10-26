import filecmp
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
        bmr_fields = list(mask_table.find_all("BMR\\d+BND\\d+"))
        assert len(bmr_fields) == subheader["NBPC"].value * subheader["NBPR"].value
        assert all(
            [field.name.endswith("00000") for field in bmr_fields]
        )  # single band
        block_size = (
            subheader["NPPBV"].value
            * subheader["NPPBV"].value
            * subheader["NBPP"].value
            // 8
        )
        included_offsets = [
            field.value
            for field in bmr_fields
            if field.value != jbpy.image_data.BLOCK_NOT_RECORDED
        ]

        assert len(included_offsets) < len(
            bmr_fields
        )  # make sure this dataset omits a block

        assert (
            jbp["FileHeader"]["LI002"].value
            == block_size * len(included_offsets) + mask_table["IMDATOFF"].value
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
        block_infos = jbpy.image_data.nominal_block_info(
            jbp["ImageSegments"][1]["subheader"]
        )
        block_infos = jbpy.image_data.apply_mask_table_to_block_info(
            jbp["ImageSegments"][1]["subheader"], block_infos, mask_table
        )

        assert len(block_infos) == (subheader["NBPC"].value * subheader["NBPR"].value)

        assert block_infos[0]["block_band_index"] == 0
        assert block_infos[0]["block_row_index"] == 0
        assert block_infos[0]["block_col_index"] == 0
        assert block_infos[0]["offset"] == mask_table["IMDATOFF"].value
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

        assert block_infos[0]["has_pad"] == (mask_table["TMRLNTH"].value == 4)
        assert block_infos[0]["pad_value"] == mask_table["TPXCD"].value

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


@pytest.mark.parametrize("with_block_mask", (False, True))
@pytest.mark.parametrize("imode", ("B", "R", "P", "S"))
def test_blocked_rgb_image(with_block_mask, imode, tmp_path):
    image = np.random.default_rng(123).integers(
        0, 255, size=(321, 451, 3), dtype=np.uint8
    )
    block_shape = np.ceil((np.asarray(image.shape[:2]) + 1) / (4, 5)).astype(int)
    num_bands = 3
    assert image.shape[-1] == num_bands
    assert np.all((image.shape[:2] % block_shape) > 0)  # require fill
    num_blocks = np.ceil(image.shape[:2] / block_shape).astype(np.uint32)
    band_axis = {"B": 0, "R": 1, "P": 2, "S": 0}[imode]
    array = np.moveaxis(image, -1, band_axis)
    expected = np.zeros_like(array)

    jbp = jbpy.Jbp()
    jbp["FileHeader"]["NUMI"].value = 1
    subhdr = jbp["ImageSegments"][0]["subheader"]
    subhdr["NROWS"].value = image.shape[0]
    subhdr["NCOLS"].value = image.shape[1]
    subhdr["IREP"].value = "RGB"
    subhdr["NBANDS"].value = num_bands
    subhdr["IREPBAND00001"].value = "R"
    subhdr["IREPBAND00002"].value = "G"
    subhdr["IREPBAND00003"].value = "B"
    subhdr["IMODE"].value = imode
    if with_block_mask:
        subhdr["IC"].value = "NM"
    else:
        subhdr["IC"].value = "NC"
    subhdr["PVTYPE"].value = "INT"
    subhdr["NBPP"].value = 8
    subhdr["ABPP"].value = 8
    subhdr["NPPBV"].value = block_shape[0]
    subhdr["NPPBH"].value = block_shape[1]
    subhdr["NBPC"].value = num_blocks[0]
    subhdr["NBPR"].value = num_blocks[1]

    mask_table = jbpy.image_data.MaskTable("mask", subhdr)
    mask_table["BMRLNTH"].value = 4

    block_info = jbpy.image_data.nominal_block_info(subhdr)
    num_expected_blocks = np.prod(num_blocks)
    if imode == "S":
        num_expected_blocks *= num_bands
    assert len(block_info) == num_expected_blocks

    included_block_info = []
    offset = 0
    for count, info in enumerate(block_info):
        block_index = (
            info["block_col_index"] + info["block_row_index"] * subhdr["NBPR"].value
        )

        bmr_name = mask_table.bmr_name(block_index, info["block_band_index"])

        omit = False
        if with_block_mask:
            if imode == "S":
                if info["block_band_index"] == 0:  # RED
                    if info["block_row_index"] == info["block_col_index"]:
                        omit = True
                if info["block_band_index"] == 1:  # GREEN
                    if info["block_row_index"] % 2 == 0:
                        omit = True
                if info["block_band_index"] == 2:  # BLUE
                    if info["block_col_index"] % 3 == 0:
                        omit = True
            else:
                omit = count % 3 == 0

        if with_block_mask and omit:
            mask_table[bmr_name].value = jbpy.image_data.BLOCK_NOT_RECORDED
        else:
            expected[info["image_slicing"]] = array[info["image_slicing"]]
            included_block_info.append(info)
            mask_table[bmr_name].value = offset
            offset += info["nbytes"]

    mask_table["IMDATOFF"].value = mask_table.get_size()

    if with_block_mask:
        jbp["FileHeader"]["LI001"].value = (
            len(included_block_info) * block_info[0]["nbytes"] + mask_table.get_size()
        )
    else:
        jbp["FileHeader"]["LI001"].value = (
            len(included_block_info) * block_info[0]["nbytes"]
        )
    filename = tmp_path / "blocked.ntf"
    jbp.finalize()
    with filename.open("wb") as file:
        jbp.dump(file)
        if with_block_mask:
            jbpy.image_data.write_uncompressed_image_data(
                jbp, 0, file, array, mask_table
            )
        else:
            jbpy.image_data.write_uncompressed_image_data(jbp, 0, file, array)

    with filename.open("rb") as file:
        jbp2 = jbpy.Jbp()
        jbp2.load(file)
        read_array, _ = jbpy.image_data.read_uncompressed_image_data(jbp2, 0, file)
        np.testing.assert_array_equal(read_array, expected)


def find_supported_jitc_cases():
    root_dir = os.environ.get("JBPY_JITC_QUICKLOOK_DIR")
    files = []
    if root_dir is not None:
        for candidate in pathlib.Path(root_dir).glob("**/*IMG_POS*.ntf"):
            jbp = jbpy.Jbp()
            with candidate.open("rb") as file:
                jbp.load(file)
                compressions = set(
                    imseg["subheader"]["IC"].value for imseg in jbp["ImageSegments"]
                )
                if compressions <= set(jbpy.image_data.COMPRESSION_READERS):
                    files.append(candidate)
    return files


def get_num_bands(subheader):
    if subheader["NBANDS"].value != 0:
        return subheader["NBANDS"].value
    return subheader["XBANDS"].value


@pytest.mark.skipif(
    "JBPY_JITC_QUICKLOOK_DIR" not in os.environ,
    reason="requires JITC Quick-Look data",
)
@pytest.mark.parametrize("filename", find_supported_jitc_cases())
def test_roundtrip(filename, tmp_path):
    rt_filename = tmp_path / "rt.ntf"
    jbp = jbpy.Jbp()
    with filename.open("rb") as ifile, rt_filename.open("wb") as ofile:
        jbp.load(ifile)
        jbp.dump(ofile)
        for idx, imseg in enumerate(jbp["ImageSegments"]):
            image, band_axis = jbpy.image_data.read_image_data(jbp, idx, ifile)
            assert image.ndim == 3
            assert image.shape[band_axis] == get_num_bands(imseg["subheader"])

            if "M" in imseg["subheader"]["IC"].value:
                mask_table = jbpy.image_data.read_mask_table(imseg, ifile)
                jbpy.image_data.write_uncompressed_image_data(
                    jbp, idx, ofile, image, mask_table=mask_table
                )
            else:
                mask_table = None
                jbpy.image_data.write_uncompressed_image_data(jbp, idx, ofile, image)

    filecmp.cmp(filename, rt_filename)


def test_byteswap(tmp_path):
    jbp = jbpy.Jbp()
    shape = (1000, 2000)
    image = np.random.default_rng(123).integers(0, 2**16 - 1, size=shape, dtype="<u2")

    jbp = jbpy.Jbp()
    jbp["FileHeader"]["NUMI"].value = 1
    imseg = jbp["ImageSegments"][0]
    subhdr = imseg["subheader"]
    subhdr["NROWS"].value = image.shape[0]
    subhdr["NCOLS"].value = image.shape[1]
    subhdr["IREP"].value = "MONO"
    subhdr["NBANDS"].value = 1
    subhdr["IREPBAND00001"].value = "M"
    subhdr["IMODE"].value = "B"
    subhdr["IC"].value = "NC"
    subhdr["PVTYPE"].value = "INT"
    subhdr["NBPP"].value = 16
    subhdr["ABPP"].value = 16
    subhdr["NPPBV"].value = 0
    subhdr["NPPBH"].value = 0
    subhdr["NBPC"].value = 1
    subhdr["NBPR"].value = 1
    imseg["Data"].size = image.nbytes
    jbp.finalize()

    output_file = tmp_path / "file.ntf"

    with output_file.open("wb") as ofile:
        jbp.dump(ofile)
        # testing for both single band 2D and automatic byteswapping
        assert image.ndim == 2
        assert image.dtype == image.dtype.newbyteorder("<")
        jbpy.image_data.write_uncompressed_image_data(
            jbp,
            0,
            ofile,
            image,
        )

    with output_file.open("rb") as file:
        jbp2 = jbpy.Jbp()
        jbp2.load(file)
        image2, band_index = jbpy.image_data.read_image_data(jbp2, 0, file)
        assert band_index == 0
        assert image2.shape == (1,) + image.shape
        assert image2.dtype == ">u2"
        np.testing.assert_array_equal(image2[0], image)
