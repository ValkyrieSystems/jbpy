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
