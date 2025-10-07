import io

import jbpy


def test_stdidc():
    tre = jbpy.tre_factory("STDIDC")
    tre.finalize()
    buf = io.BytesIO()
    tre.dump(buf)
    assert tre["CETAG"].value == "STDIDC"
    assert tre["CEL"].value == 89
    assert buf.tell() == tre["CEL"].value + 11
