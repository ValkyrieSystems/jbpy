import json
import os
import subprocess

import pytest

import jbpy.core
import test.utils


def empty_nitf():
    ntf = jbpy.core.Jbp()
    ntf["FileHeader"]["OSTAID"].value = "Here"
    ntf["FileHeader"]["FSCLAS"].value = "U"
    return ntf


def test_jbpinfo(tmp_path):
    filename = tmp_path / "empty.ntf"
    with filename.open("wb") as file:
        empty_nitf().dump(file)

    proc = subprocess.run(["jbpinfo", filename], check=True, capture_output=True)
    assert "OSTAID" in proc.stdout.decode()

    proc = subprocess.run(
        ["jbpinfo", filename, "--format", "json"], check=True, capture_output=True
    )
    data = json.loads(proc.stdout.decode())
    assert data["FileHeader"]["OSTAID"] == "Here"

    proc = subprocess.run(
        ["jbpinfo", filename, "--format", "json-full"], check=True, capture_output=True
    )
    datafull = json.loads(proc.stdout.decode())
    assert datafull["FileHeader"]["OSTAID"]["value"] == "Here"
    assert "offset" in datafull["FileHeader"]["OSTAID"]


@pytest.mark.skipif(
    "JBPY_JITC_QUICKLOOK_DIR" not in os.environ,
    reason="requires JITC Quick-Look data",
)
@pytest.mark.parametrize("filename", test.utils.find_jitcs_test_files())
@pytest.mark.parametrize("format", ("text", "json", "json-full"))
def test_jbpinfo_jitc(filename, format):
    subprocess.run(
        ["jbpinfo", filename, "--format", format], check=True, capture_output=True
    )


def test_smart_open(tmp_path):
    filename = tmp_path / "empty.ntf"
    with filename.open("wb") as file:
        empty_nitf().dump(file)

    with test.utils.static_http_server(filename.parent) as server_url:
        proc = subprocess.run(
            ["jbpinfo", f"{server_url}/{filename.name}", "--format", "json"],
            stdout=subprocess.PIPE,
            check=True,
        )

        info = json.loads(proc.stdout)
        assert info
