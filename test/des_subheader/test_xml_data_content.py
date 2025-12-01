import pytest

import jbpy


def test_xml_data_content():
    subheader = jbpy.des_subheader_factory("XML_DATA_CONTENT", 1)
    assert "DESSHF" not in subheader

    with pytest.raises(ValueError):
        subheader["DESSHL"].value = 1  # must exactly match a length of fields

    subheader["DESSHL"].value = 5
    assert "DESCRC" in subheader
    assert "DESSHFT" not in subheader

    subheader["DESSHL"].value = 283
    assert "DESCRC" in subheader
    assert "DESSHFT" in subheader
    assert "DESSHLPG" not in subheader

    subheader["DESSHL"].value = 773
    assert "DESCRC" in subheader
    assert "DESSHFT" in subheader
    assert "DESSHLPG" in subheader
    assert "DESSHABS" in subheader
