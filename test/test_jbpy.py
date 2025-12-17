import io
import os

import pytest

import jbpy
import test.utils


@pytest.mark.skipif(
    "JBPY_JITC_QUICKLOOK_DIR" not in os.environ,
    reason="requires JITC Quick-Look data",
)
@pytest.mark.parametrize("filename", test.utils.find_jitcs_test_files())
def test_roundtrip_jitc_quicklook(filename, tmp_path):
    ntf = jbpy.Jbp()
    with filename.open("rb") as file:
        ntf.load(file)

    copy_filename = tmp_path / "copy.nitf"
    with copy_filename.open("wb") as fd:
        ntf.dump(fd)

    ntf2 = jbpy.Jbp()
    with copy_filename.open("rb") as file:
        ntf2.load(file)

    assert ntf == ntf2

    file_components_to_compare = [ntf["FileHeader"]]
    for segtype in list(ntf.values())[1:]:
        file_components_to_compare.extend(x["subheader"] for x in segtype)
    for component in file_components_to_compare:
        with filename.open("rb") as f_orig, copy_filename.open("rb") as f_copy:
            offset = component.get_offset()
            size = component.get_size()
            f_orig.seek(offset)
            bytes_orig = f_orig.read(size)
            f_copy.seek(offset)
            bytes_copy = f_copy.read(size)
            assert bytes_orig == bytes_copy


EXPECTED_TRES = (
    "BLOCKA",
    "EXOPTA",
    "GEOPSB",
    "ICHIPB",
    "J2KLRA",
    "PRJPSB",
    "REGPTB",
    "RPC00B",
    "SECTGA",
    "STDIDC",
    "USE00A",
)


def test_available_tres_match_expected():
    all_tres = jbpy.available_tres()
    assert set(all_tres).issuperset(EXPECTED_TRES)

    for trename in all_tres:
        assert isinstance(jbpy.tre_factory(trename), all_tres[trename])


@pytest.mark.parametrize("trename", EXPECTED_TRES)
def test_tre_factory(trename):
    tre = jbpy.tre_factory(trename)
    tre.finalize()
    buf = io.BytesIO()
    tre.dump(buf)
    assert tre[tre.tretag_rename].value == trename
    assert buf.tell() == tre[tre.trel_rename].value + 11

    buf.seek(0)
    tre2 = jbpy.tre_factory(trename)
    tre2.load(buf)
    assert tre == tre2


EXPECTED_DES_SUBHEADERS: tuple[str, int] = (
    # (DESID, DESVER)
    ("TRE_OVERFLOW", 1),
    ("XML_DATA_CONTENT", 1),
)


def test_available_des_subheaders_match_expected():
    all_des_subheaders = jbpy.available_des_subheaders()
    assert set(all_des_subheaders).issuperset(EXPECTED_DES_SUBHEADERS)


@pytest.mark.parametrize("desidver", EXPECTED_DES_SUBHEADERS)
def test_des_subheader_factory(desidver):
    this_name = "".join(map(str, desidver))
    des_subhdr = jbpy.des_subheader_factory(*desidver, name=this_name)
    des_subhdr.finalize()
    assert des_subhdr.name == this_name
    assert des_subhdr["DESID"].value == desidver[0]
    assert des_subhdr["DESVER"].value == desidver[1]
    buf = io.BytesIO()
    des_subhdr.dump(buf)
    positive_desshl = des_subhdr["DESSHL"].value > 0
    has_userdefined_fields = any(
        f.get_offset() > des_subhdr["DESSHL"].get_offset() for f in des_subhdr.values()
    )
    assert positive_desshl == has_userdefined_fields

    buf.seek(0)
    des_subhdr2 = jbpy.des_subheader_factory(*desidver)
    des_subhdr2.load(buf)
    assert des_subhdr == des_subhdr2
