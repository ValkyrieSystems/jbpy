import datetime
import filecmp
import io
import logging
import os
import pathlib
import random
import string
import tempfile

import pytest

import jbpy.core


def test_string_ascii_conv(caplog):
    conv = jbpy.core.StringAscii("test", 5)
    assert conv.to_bytes("") == b"     "
    assert conv.to_bytes("abc") == b"abc  "
    assert conv.to_bytes("abcde") == b"abcde"
    with caplog.at_level(logging.WARNING, logger="jbpy.core"):
        assert conv.to_bytes("abcdef") == b"abcde"
        assert len(caplog.records) == 1
        assert "truncated" in caplog.records[0].message
    with pytest.raises(ValueError):
        conv.to_bytes("\N{LATIN CAPITAL LETTER O WITH STROKE}")

    assert conv.from_bytes(b"     ") == ""
    assert conv.from_bytes(b"abc  ") == "abc"
    assert conv.from_bytes(b"abcde") == "abcde"
    with pytest.raises(ValueError):
        conv.from_bytes(b"\xd8")


def test_string_iso_conv(caplog):
    conv = jbpy.core.StringISO8859_1("test", 5)
    assert conv.to_bytes("") == b"     "
    assert conv.to_bytes("abc") == b"abc  "
    assert conv.to_bytes("abcde") == b"abcde"
    with caplog.at_level(logging.WARNING, logger="jbpy.core"):
        assert conv.to_bytes("abcdef") == b"abcde"
        assert len(caplog.records) == 1
        assert "truncated" in caplog.records[0].message
    assert conv.to_bytes("\N{LATIN CAPITAL LETTER O WITH STROKE}") == b"\xd8    "

    assert conv.from_bytes(b"     ") == ""
    assert conv.from_bytes(b"abc  ") == "abc"
    assert conv.from_bytes(b"abcde") == "abcde"
    assert conv.from_bytes(b"\xd8") == "\N{LATIN CAPITAL LETTER O WITH STROKE}"


def test_string_utf8_conv(caplog):
    conv = jbpy.core.StringUtf8("test", 5)
    assert conv.to_bytes("") == b"     "
    assert conv.to_bytes("abc") == b"abc  "
    assert conv.to_bytes("abcde") == b"abcde"
    with caplog.at_level(logging.WARNING, logger="jbpy.core"):
        assert conv.to_bytes("abcdef") == b"abcde"
        assert len(caplog.records) == 1
        assert "truncated" in caplog.records[0].message
    assert conv.to_bytes("\N{LATIN CAPITAL LETTER O WITH STROKE}") == b"\xc3\x98   "

    assert conv.from_bytes(b"     ") == ""
    assert conv.from_bytes(b"abc  ") == "abc"
    assert conv.from_bytes(b"abcde") == "abcde"
    assert conv.from_bytes(b"\xc3\x98") == "\N{LATIN CAPITAL LETTER O WITH STROKE}"


def test_bytes_conv():
    conv = jbpy.core.Bytes("test", 5)
    assert conv.to_bytes(b"asdf") == b"asdf"
    assert conv.from_bytes(b"asdf") == b"asdf"


def test_integer_conv(caplog):
    conv = jbpy.core.Integer("test", 5)
    assert conv.to_bytes(0) == b"00000"
    assert conv.to_bytes(10) == b"00010"
    assert conv.to_bytes(-123) == b"-0123"
    with caplog.at_level(logging.WARNING, logger="jbpy.core"):
        assert conv.to_bytes(123456) == b"12345"
        assert len(caplog.records) == 1
        assert "truncated" in caplog.records[0].message

    assert conv.from_bytes(b"00000") == 0
    assert conv.from_bytes(b"00010") == 10
    assert conv.from_bytes(b"-0123") == -123


def test_rgb_conv():
    conv = jbpy.core.RGB("test", 3)
    assert conv.to_bytes((1, 2, 3)) == b"\01\02\03"
    assert conv.from_bytes(b"\01\02\03") == (1, 2, 3)


def test_segmentlist():
    seglist = jbpy.core.SegmentList(
        "test", lambda n: jbpy.core.ImageSegment(n, None), minimum=2, maximum=4
    )
    assert len(seglist) == 2
    seglist.set_count(4)
    assert len(seglist) == 4
    assert isinstance(seglist[-1], jbpy.core.ImageSegment)
    with pytest.raises(ValueError):
        seglist.set_count(5)
    with pytest.raises(ValueError):
        seglist.set_count(1)


def test_range_any():
    check = jbpy.core.AnyRange()
    assert check.isvalid(1)
    assert check.isvalid("")
    assert check.isvalid("a")


def test_range_minmax():
    check = jbpy.core.MinMax(-10, 10)
    assert not check.isvalid(-10.1)
    assert check.isvalid(-10)
    assert check.isvalid(0)
    assert check.isvalid(10)
    assert not check.isvalid(10.1)


def test_range_regex():
    check = jbpy.core.Regex("[abc]+")
    assert check.isvalid("aa")
    assert check.isvalid("cb")
    assert not check.isvalid("ad")
    assert not check.isvalid("")


def test_range_constant():
    check = jbpy.core.Constant("foobar")
    assert check.isvalid("foobar")
    assert not check.isvalid("foobar1")
    assert not check.isvalid("1foobar")


def test_range_enum():
    check = jbpy.core.Enum(["A", "B"])
    assert check.isvalid("A")
    assert check.isvalid("B")
    assert not check.isvalid("C")


def test_range_anyof():
    check = jbpy.core.AnyOf(
        jbpy.core.Constant("A"),
        jbpy.core.Constant("B"),
    )
    assert check.isvalid("A")
    assert check.isvalid("B")
    assert not check.isvalid("C")

    # AnyOf short-circuits
    class RaisesError(jbpy.core.RangeCheck):
        def isvalid(self, decoded_value):
            raise ValueError()

    with pytest.raises(Exception):
        jbpy.core.AnyOf(RaisesError()).isvalid("A")
    assert jbpy.core.AnyOf(jbpy.core.Constant("A"), RaisesError()).isvalid("A")


def test_range_not():
    check = jbpy.core.Not(
        jbpy.core.Constant("A"),
    )
    assert not check.isvalid("A")
    assert check.isvalid("B")


def empty_nitf():
    ntf = jbpy.core.Jbp()
    ntf["FileHeader"]["OSTAID"].value = "Here"
    ntf["FileHeader"]["FSCLAS"].value = "U"
    return ntf


def add_imseg(ntf):
    ntf["FileHeader"]["NUMI"].value += 1
    idx = ntf["FileHeader"]["NUMI"].value - 1
    ntf["ImageSegments"][idx]["subheader"]["IID1"].value = "Unit Test"
    ntf["ImageSegments"][idx]["subheader"]["IDATIM"].value = datetime.datetime(
        1955, 11, 5
    ).strftime("%Y%m%d%H%M%S")
    ntf["ImageSegments"][idx]["subheader"]["ISCLAS"].value = "U"
    ntf["ImageSegments"][idx]["subheader"]["PVTYPE"].value = "INT"
    ntf["ImageSegments"][idx]["subheader"]["IREP"].value = "MONO"
    ntf["ImageSegments"][idx]["subheader"]["ICAT"].value = "SAR"
    ntf["ImageSegments"][idx]["subheader"]["ABPP"].value = 8
    ntf["ImageSegments"][idx]["subheader"]["IC"].value = "NC"
    ntf["ImageSegments"][idx]["subheader"]["NBANDS"].value = 1
    ntf["ImageSegments"][idx]["subheader"]["IREPBAND00001"].value = "M"
    ntf["ImageSegments"][idx]["subheader"]["IMODE"].value = "B"
    ntf["ImageSegments"][idx]["subheader"]["NBPR"].value = 1
    ntf["ImageSegments"][idx]["subheader"]["NBPC"].value = 1
    ntf["ImageSegments"][idx]["subheader"]["NPPBH"].value = 30
    ntf["ImageSegments"][idx]["subheader"]["NPPBV"].value = 20
    ntf["ImageSegments"][idx]["subheader"]["NROWS"].value = 20
    ntf["ImageSegments"][idx]["subheader"]["NCOLS"].value = 30
    ntf["ImageSegments"][idx]["subheader"]["NBPP"].value = 8
    ntf["ImageSegments"][idx]["subheader"]["ILOC"].value = (0, 0)
    ntf["ImageSegments"][idx]["Data"].size = 20 * 30
    return ntf


def check_roundtrip(ntf):
    ntf.finalize()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = pathlib.Path(tmpdir)

        orig = tmpdir / "orig.ntf"
        second = tmpdir / "copy.ntf"
        with orig.open("wb") as fd:
            ntf.dump(fd)
        ntf2 = jbpy.core.Jbp()
        with orig.open("rb") as fd:
            ntf2.load(fd)
        assert ntf == ntf2
        with second.open("wb") as fd:
            ntf2.dump(fd)

        assert filecmp.cmp(orig, second)
    return ntf2


def test_fileheader(capsys):
    ntf = empty_nitf()
    header = ntf["FileHeader"]
    assert "UDHOFL" not in header
    header["UDHDL"].value = 10
    assert "UDHOFL" in header
    header["UDHD"].append(jbpy.core.tre_factory("SECTGA"))

    assert "XHDLOFL" not in header
    assert "XHD" not in header
    header["XHDL"].value = 10
    assert "XHDLOFL" in header
    header["XHD"].append(jbpy.core.tre_factory("SECTGA"))

    check_roundtrip(ntf)

    assert len(ntf["ImageSegments"]) == 0
    header["NUMI"].value = 2
    assert len(ntf["ImageSegments"]) == 2
    assert "LI002" in header
    header["NUMI"].value = 1
    header["LI001"].value = 10
    assert "LI002" not in header
    assert len(ntf["ImageSegments"]) == 1
    assert "LISH002" not in header
    header["NUMI"].value = 0
    assert len(ntf["ImageSegments"]) == 0
    assert "LI001" not in header
    assert "LISH001" not in header

    assert len(ntf["GraphicSegments"]) == 0
    header["NUMS"].value = 2
    assert len(ntf["GraphicSegments"]) == 2
    header["NUMS"].value = 1
    header["LS001"].value = 10
    header["LSSH001"].value = 300
    assert len(ntf["GraphicSegments"]) == 1
    # leave 1 segment to test placeholder logic
    ntf["GraphicSegments"][0]["subheader"].value = b"\0" * 300

    assert len(ntf["TextSegments"]) == 0
    header["NUMT"].value = 2
    assert len(ntf["TextSegments"]) == 2
    header["NUMT"].value = 1
    header["LT001"].value = 10
    header["LTSH001"].value = 300
    assert len(ntf["TextSegments"]) == 1
    # leave 1 segment to test placeholder logic
    ntf["TextSegments"][0]["subheader"].value = b"\0" * 300

    assert len(ntf["DataExtensionSegments"]) == 0
    header["NUMDES"].value = 2
    assert len(ntf["DataExtensionSegments"]) == 2
    header["NUMDES"].value = 1
    header["LD001"].value = 10
    assert len(ntf["DataExtensionSegments"]) == 1
    header["NUMDES"].value = 0
    assert len(ntf["DataExtensionSegments"]) == 0
    assert "LD001" not in header
    assert "LDSH001" not in header

    assert len(ntf["ReservedExtensionSegments"]) == 0
    header["NUMRES"].value = 2
    assert len(ntf["ReservedExtensionSegments"]) == 2
    header["NUMRES"].value = 1
    header["LRE001"].value = 10
    header["LRESH001"].value = 300
    assert len(ntf["ReservedExtensionSegments"]) == 1
    ntf["ReservedExtensionSegments"][0]["subheader"].value = b"\0" * 300
    # leave 1 segment to test placeholder logic

    ntf.finalize()
    ntf.print()
    captured = capsys.readouterr()
    assert "GraphicSegment" in captured.out
    assert "TextSegment" in captured.out
    assert "ReservedExtensionSegment" in captured.out


def test_imseg():
    ntf = empty_nitf()
    add_imseg(ntf)
    check_roundtrip(ntf)
    add_imseg(ntf)
    assert ntf["FileHeader"]["NUMI"].value == 2
    check_roundtrip(ntf)
    subheader = ntf["ImageSegments"][0]["subheader"]
    assert "IGEOLO" not in subheader
    subheader["ICORDS"].value = "G"
    assert "IGEOLO" in subheader

    assert "ICOM1" not in subheader
    subheader["NICOM"].value = 1
    subheader["ICOM1"].value = "This is a comment"

    # Change number of bands
    assert subheader["NBANDS"].value == 1
    subheader["NBANDS"].value = 2
    assert "NELUT00001" not in subheader
    assert "NELUT00002" not in subheader
    subheader["NLUTS00002"].value = 1
    assert "NELUT00001" not in subheader
    assert "NELUT00002" in subheader
    subheader["NELUT00002"].value = 4
    assert subheader["LUTD000021"].size == 4
    subheader["LUTD000021"].value = b"\0" * 4

    check_roundtrip(ntf)

    assert "XBANDS" not in subheader
    subheader["NBANDS"].value = 0
    assert "XBANDS" in subheader
    assert "IREPBAND00001" not in subheader
    assert "IREPBAND00010" not in subheader
    subheader["XBANDS"].value = 10
    assert "IREPBAND00001" in subheader
    assert "IREPBAND00010" in subheader

    check_roundtrip(ntf)

    assert "COMRAT" not in subheader
    subheader["IC"].value = "C7"
    assert "COMRAT" in subheader

    assert "UDOFL" not in subheader
    assert "UDID" not in subheader
    subheader["UDIDL"].value = 100
    assert "UDOFL" in subheader
    assert "UDID" in subheader
    assert len(subheader["UDID"]) == 0  # NO TREs

    assert "IXSOFL" not in subheader
    assert "IXSHD" not in subheader
    subheader["IXSHDL"].value = 100
    assert "IXSOFL" in subheader
    assert "IXSHD" in subheader


def test_deseg():
    ntf = empty_nitf()
    assert ntf["FileHeader"]["NUMDES"].value == 0
    assert len(ntf["DataExtensionSegments"]) == 0
    ntf["FileHeader"]["NUMDES"].value += 1
    assert len(ntf["DataExtensionSegments"]) == 1

    ntf["DataExtensionSegments"][0]["DESDATA"].size = 10

    subheader = ntf["DataExtensionSegments"][0]["subheader"]
    subheader["DESID"].value = "mydesid"
    subheader["DESVER"].value = 1
    subheader["DESCLAS"].value = "U"
    assert "DESSHF" not in subheader
    subheader["DESSHL"].value = 0
    assert "DESSHF" not in subheader
    subheader["DESSHL"].value = 10
    assert subheader["DESSHF"].size == 10
    subheader["DESSHF"].value = "abcd"

    check_roundtrip(ntf)

    # Test XML_DATA_CONTENT (see STDI-0002 Volume 2 Appendix F)
    assert isinstance(subheader["DESSHF"], jbpy.core.Field)
    subheader["DESID"].value = "XML_DATA_CONTENT"
    subheader["DESVER"].value = 1

    subheader["DESSHL"].value = 0
    assert "DESSHF" not in subheader

    with pytest.raises(ValueError):
        subheader["DESSHL"].value = 1  # must exactly match a length of fields

    subheader["DESSHL"].value = 5
    assert "DESCRC" in subheader["DESSHF"]
    assert "DESSHFT" not in subheader["DESSHF"]

    subheader["DESSHL"].value = 283
    assert "DESCRC" in subheader["DESSHF"]
    assert "DESSHFT" in subheader["DESSHF"]
    assert "DESSHLPG" not in subheader["DESSHF"]

    subheader["DESSHL"].value = 773
    assert "DESCRC" in subheader["DESSHF"]
    assert "DESSHFT" in subheader["DESSHF"]
    assert "DESSHLPG" in subheader["DESSHF"]
    assert "DESSHABS" in subheader["DESSHF"]

    # Fill out fields that don't have default values
    subheader["DESSHF"]["DESSHFT"].value = "XML"
    subheader["DESSHF"]["DESSHDT"].value = "1955-11-05"
    subheader["DESSHF"]["DESSHSD"].value = "2015-10-21"
    check_roundtrip(ntf)


def test_field(caplog):
    callbackinfo = {"called": False}

    def callback(fld):
        callbackinfo["called"] = True

    field = jbpy.core.Field(
        "MyField",
        "Description",
        5,
        jbpy.core.BCSN,
        jbpy.core.MinMax(10, 100),
        jbpy.core.Integer,
        default=0,
        setter_callback=callback,
    )
    assert not callbackinfo["called"]
    field.size = 6
    assert callbackinfo["called"]
    field.value = 50
    assert field.isvalid()
    assert field.value == 50
    assert field.encoded_value == b"000050"
    field.value = 1
    assert not field.isvalid()

    with pytest.raises(ValueError):
        stream = io.BytesIO(b"abcdefghi")
        field.load(stream)

    field = jbpy.core.Field(
        "MyField",
        "Description",
        5,
        jbpy.core.BCSN,
        jbpy.core.AnyRange(),
        jbpy.core.StringUtf8,
        default="",
    )

    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="jbpy.core"):
        stream = io.BytesIO(b"abcdefghi")
        field.load(stream)
        assert len(caplog.records) == 1
        assert "Invalid" in caplog.records[0].message

    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="jbpy.core"):
        field.value = "abc"
        assert len(caplog.records) == 1
        assert "Invalid" in caplog.records[0].message

    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="jbpy.core"):
        # "invalid" default does not result in a warning
        jbpy.core.Field(
            "MyField",
            "Description",
            5,
            jbpy.core.BCSN,
            jbpy.core.AnyRange(),
            jbpy.core.StringUtf8,
            default="abc",
        )
        assert not caplog.records


def test_binaryplaceholder():
    bp = jbpy.core.BinaryPlaceholder("placeholder", 10)
    initial_data = b"0123456789"
    stream = io.BytesIO(initial_data)
    start = stream.tell()
    bp.dump(stream)
    stop = stream.tell()
    assert stop - start == 10
    assert stream.getvalue() == initial_data


def test_clevel():
    ntf = empty_nitf()
    ntf["FileHeader"]["NUMI"].value = 2
    ntf["ImageSegments"][0]["subheader"]["IDLVL"].value = 1
    ntf["ImageSegments"][0]["subheader"]["IALVL"].value = 0
    ntf["ImageSegments"][0]["subheader"]["ILOC"].value = (500, 500)
    ntf["ImageSegments"][0]["subheader"]["NROWS"].value = 1000
    ntf["ImageSegments"][0]["subheader"]["NCOLS"].value = 1000

    ntf["ImageSegments"][1]["subheader"]["IDLVL"].value = 2
    ntf["ImageSegments"][1]["subheader"]["IALVL"].value = 1
    ntf["ImageSegments"][1]["subheader"]["ILOC"].value = (0, 0)
    ntf["ImageSegments"][1]["subheader"]["NROWS"].value = 1
    ntf["ImageSegments"][1]["subheader"]["NCOLS"].value = 1
    assert ntf._clevel_ccs_extent() == 3
    assert ntf._clevel_image_size() == 3
    ntf["ImageSegments"][1]["subheader"]["ILOC"].value = (2000, 2000)
    assert ntf._clevel_ccs_extent() == 5
    assert ntf._clevel_image_size() == 3
    ntf["ImageSegments"][1]["subheader"]["NROWS"].value = 1
    ntf["ImageSegments"][1]["subheader"]["NCOLS"].value = 1000
    assert ntf._clevel_ccs_extent() == 5
    assert ntf._clevel_image_size() == 3
    ntf["ImageSegments"][1]["subheader"]["NROWS"].value = 8000
    ntf["ImageSegments"][1]["subheader"]["NCOLS"].value = 1
    assert ntf._clevel_ccs_extent() == 6
    assert ntf._clevel_image_size() == 5
    ntf["ImageSegments"][1]["subheader"]["NROWS"].value = 1
    ntf["ImageSegments"][1]["subheader"]["NCOLS"].value = 65000
    assert ntf._clevel_ccs_extent() == 7
    assert ntf._clevel_image_size() == 6
    ntf["ImageSegments"][1]["subheader"]["NROWS"].value = 1
    ntf["ImageSegments"][1]["subheader"]["NCOLS"].value = 99_999_998
    assert ntf._clevel_ccs_extent() == 9
    assert ntf._clevel_image_size() == 7

    ntf["FileHeader"]["FL"].value = 100
    assert ntf._clevel_file_size() == 3

    ntf["FileHeader"]["FL"].value = 99_999_999_999
    assert ntf._clevel_file_size() == 9

    ntf["ImageSegments"][0]["subheader"]["NPPBH"].value = 0
    ntf["ImageSegments"][0]["subheader"]["NPPBV"].value = 0
    ntf["ImageSegments"][1]["subheader"]["NPPBH"].value = 0
    ntf["ImageSegments"][1]["subheader"]["NPPBV"].value = 0
    assert ntf._clevel_image_blocking() == 3
    ntf["ImageSegments"][1]["subheader"]["NPPBH"].value = 3000
    ntf["ImageSegments"][1]["subheader"]["NPPBV"].value = 3000
    assert ntf._clevel_image_blocking() == 5


def test_unknown_tre():
    unk = jbpy.core.UnknownTre("UNK00A")
    assert unk["TREL"].value == 0
    assert unk["TREDATA"].size == 0
    unk["TREL"].value = 123
    assert unk["TREDATA"].size == 123

    unk["TREDATA"].size = 456
    unk.finalize()
    assert unk["TREL"].value == 456


def add_txtseg(ntf):
    ntf["FileHeader"]["NUMT"].value += 1
    idx = ntf["FileHeader"]["NUMT"].value - 1
    ntf["TextSegments"][idx]["subheader"]["TEXTID"].value = "Unit Te"
    ntf["TextSegments"][idx]["subheader"]["TXTALVL"].value = 24
    ntf["TextSegments"][idx]["subheader"]["TXTDT"].value = datetime.datetime(
        1955, 11, 5
    ).strftime("%Y%m%d%H%M%S")
    ntf["TextSegments"][idx]["subheader"]["TXTITL"].value = "the text title"
    ntf["TextSegments"][idx]["subheader"]["TSCLAS"].value = "U"
    ntf["TextSegments"][idx]["subheader"]["TXTFMT"].value = "U8S"
    ntf["TextSegments"][idx]["Data"].size = 20 * 30
    return ntf


def test_txtseg():
    ntf = empty_nitf()
    add_txtseg(ntf)
    check_roundtrip(ntf)
    add_txtseg(ntf)
    assert ntf["FileHeader"]["NUMT"].value == 2
    check_roundtrip(ntf)
    subheader = ntf["TextSegments"][0]["subheader"]

    assert "TXSOFL" not in subheader
    assert "TXSHD" not in subheader
    subheader["TXSHDL"].value = 100
    assert "TXSOFL" in subheader
    assert "TXSHD" in subheader


def add_graphicseg(ntf):
    ntf["FileHeader"]["NUMS"].value += 1
    idx = ntf["FileHeader"]["NUMS"].value - 1
    ntf["GraphicSegments"][idx]["subheader"]["SID"].value = "Unit Test"
    ntf["GraphicSegments"][idx]["subheader"]["SNAME"].value = "S is for graphic"
    ntf["GraphicSegments"][idx]["subheader"]["SSCLAS"].value = "U"
    ntf["GraphicSegments"][idx]["subheader"]["SLOC"].value = (0, 1)
    ntf["GraphicSegments"][idx]["subheader"]["SBND1"].value = (2, 3)
    ntf["GraphicSegments"][idx]["subheader"]["SBND2"].value = (4, 5)
    ntf["GraphicSegments"][idx]["Data"].size = 20 * 30
    return ntf


def test_graphicseg():
    ntf = empty_nitf()
    add_graphicseg(ntf)
    check_roundtrip(ntf)
    add_graphicseg(ntf)
    assert ntf["FileHeader"]["NUMS"].value == 2
    check_roundtrip(ntf)
    subheader = ntf["GraphicSegments"][0]["subheader"]

    assert "SXSOFL" not in subheader
    assert "SXSHD" not in subheader
    subheader["SXSHDL"].value = 100
    assert "SXSOFL" in subheader
    assert "SXSHD" in subheader


def test_as_filelike(tmp_path):
    empty = empty_nitf()
    filename = tmp_path / "file.nitf"
    with filename.open("wb") as file:
        empty.dump(file)

    with filename.open("rb") as file:
        ntf = jbpy.core.Jbp().load(file)
        subfile = ntf["FileHeader"]["OSTAID"].as_filelike(file)
        assert subfile.read() == b"Here      "


def test_subfile(tmp_path):
    filename = tmp_path / "random.bin"
    all_data = bytearray(
        "".join(random.choices(string.ascii_letters + string.digits, k=1000)).encode()
    )
    all_data[500] = ord("\n")
    all_data[550] = ord("\n")
    all_data[600] = ord("\n")
    filename.write_bytes(all_data)

    with filename.open("rb") as file:
        start = 11
        length = 22
        subfile = jbpy.core.SubFile(file, start, length)
        assert subfile.tell() == 0
        assert subfile.read() == all_data[start : start + length]
        expected_pos = length
        assert subfile.tell() == expected_pos
        subfile.seek(1)
        expected_pos = 1
        assert (
            subfile.read(5) == all_data[start + expected_pos : start + expected_pos + 5]
        )
        expected_pos += 5
        subfile.seek(1, os.SEEK_CUR)
        expected_pos += 1
        assert subfile.tell() == expected_pos
        assert (
            subfile.read(5) == all_data[start + expected_pos : start + expected_pos + 5]
        )
        subfile.seek(-2, os.SEEK_END)
        expected_pos = length - 2
        assert subfile.tell() == expected_pos
        subfile.seek(length + 100)
        assert subfile.read() == b""

        expected_pos = 100
        subfile.seek(expected_pos)
        ba = bytearray(50)
        assert subfile.readinto(ba) == len(ba)
        assert ba == all_data[start + expected_pos : start + expected_pos + len(ba)]

        expected_pos = 400
        subfile.seek(expected_pos)
        assert (
            subfile.readline(3)
            == all_data[start + expected_pos : start + expected_pos + 3]
        )
        assert subfile.readline() == all_data[start + expected_pos + 3 : 501]
        assert subfile.readlines() == [
            all_data[501:551],
            all_data[551:601],
            all_data[601:],
        ]

        expected_pos = 400
        subfile.seek(offset=expected_pos)
        assert subfile.readlines(95) == [
            all_data[start + expected_pos : 501],
            all_data[501:551],
        ]
