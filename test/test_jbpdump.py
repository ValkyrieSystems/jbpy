import os
import pathlib
import subprocess

import pytest

import jbpy
import test.utils


def find_jitc_ql_app_pos_01():
    # See https://jitc.fhu.disa.mil/projects/nitf/testdata.aspx
    root_dir = pathlib.Path(os.environ.get("JBPY_JITC_QUICKLOOK_DIR"))
    candidates = list(root_dir.glob("**/NITF_ALL_POS_01.ntf"))
    assert len(candidates) == 1
    return candidates[0]


@pytest.mark.skipif(
    "JBPY_JITC_QUICKLOOK_DIR" not in os.environ,
    reason="requires JITC Quick-Look data",
)
def test_jitc_quicklook():
    filename = find_jitc_ql_app_pos_01()

    jbp = jbpy.Jbp()
    with filename.open("rb") as file:
        jbp.load(file)

    proc = subprocess.run(
        ["jbpdump", filename, "--text-segment", "2"], check=True, capture_output=True
    )
    assert proc.stdout == b"#3"

    assert jbp["ImageSegments"][0]["subheader"]["IC"].value == "C3"
    proc = subprocess.run(
        ["jbpdump", filename, "--image-segment", "0"], check=True, capture_output=True
    )
    assert len(proc.stdout) == jbp["FileHeader"]["LI001"].value
    assert proc.stdout[:2] == b"\xff\xd8"  # JPEG SOI marker
    assert proc.stdout[-2:] == b"\xff\xd9"  # JPEG EOI marker

    proc = subprocess.run(
        ["jbpdump", filename, "--image-segment", "2"], check=True, capture_output=True
    )
    assert len(proc.stdout) == jbp["FileHeader"]["LI003"].value

    proc = subprocess.run(
        ["jbpdump", filename, "--graphic-segment", "2"], check=True, capture_output=True
    )
    assert proc.stdout[:2] == b"\x00\x21"  # CGM BEGIN METAFILE
    assert proc.stdout[-2:] == b"\x00\x40"  # CGM END METAFILE


@pytest.mark.skipif(
    "JBPY_JITC_QUICKLOOK_DIR" not in os.environ,
    reason="requires JITC Quick-Look data",
)
def test_smart_open(tmp_path):
    filename = find_jitc_ql_app_pos_01()

    with test.utils.static_http_server(filename.parent) as server_url:
        proc = subprocess.run(
            ["jbpdump", f"{server_url}/{filename.name}", "--image-segment", "0"],
            check=True,
            capture_output=True,
        )
        assert proc.stdout[:2] == b"\xff\xd8"  # JPEG SOI marker
        assert proc.stdout[-2:] == b"\xff\xd9"  # JPEG EOI marker
