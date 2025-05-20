import io

import jbpy


def test_sectga():
    sectga = jbpy.tre_factory("SECTGA")
    sectga.finalize()
    buf = io.BytesIO()
    sectga.dump(buf)
    assert sectga["CETAG"].value == "SECTGA"
    assert sectga["CEL"].value == 28
    assert buf.tell() == sectga["CEL"].value + 11
