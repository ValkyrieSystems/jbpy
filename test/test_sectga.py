import io

import pybiif


def test_sectga():
    sectga = pybiif.tre_factory("SECTGA")
    sectga.finalize()
    buf = io.BytesIO()
    sectga.dump(buf)
    assert sectga["CETAG"].value == "SECTGA"
    assert sectga["CEL"].value == 28
    assert buf.tell() == sectga["CEL"].value + 11
