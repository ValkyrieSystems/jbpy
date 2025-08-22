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


def test_available_tres():
    all_tres = jbpy.available_tres()
    assert "SECTGA" in all_tres
    for trename in all_tres:
        assert isinstance(jbpy.tre_factory(trename), all_tres[trename])
