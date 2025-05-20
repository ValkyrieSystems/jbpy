import os
import pathlib

import pytest

import jbpy


def find_jitcs_test_files():
    # See https://jitc.fhu.disa.mil/projects/nitf/testdata.aspx
    root_dir = os.environ.get("JBPY_JITC_QUICKLOOK_DIR")
    files = []
    if root_dir is not None:
        root_dir = pathlib.Path(root_dir)
        files += list(root_dir.glob("**/*POS*.NTF"))
        files += list(root_dir.glob("**/*POS*.ntf"))
    return files


@pytest.mark.skipif(
    "JBPY_JITC_QUICKLOOK_DIR" not in os.environ,
    reason="requires JITC Quick-Look data",
)
@pytest.mark.parametrize("filename", find_jitcs_test_files())
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
