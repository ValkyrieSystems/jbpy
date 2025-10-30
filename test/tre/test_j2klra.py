import jbpy

ORIG_VALUES = {
    0: "Original NPJE",
    1: "Parsed NPJE",
    2: "Original EPJE",
    3: "Parsed EPJE",
    4: "Original TPJE",
    5: "Parsed TPJE",
    6: "Original LPJE",
    7: "Parsed LPJE",
    8: "Original other",
    9: "Parsed other",
}


def test_conditional_fields():
    tre = jbpy.tre_factory("J2KLRA")
    for orig in range(10):
        tre["ORIG"].value = orig
        for field in ("NLEVELS_I", "NBANDS_I", "NLAYERS_I"):
            assert (field in tre) == (ORIG_VALUES[orig].startswith("Parsed"))

    # value persists even if pre-requisite field is changed
    tre["NLEVELS_I"].value = 24
    tre["ORIG"].value = 1
    assert tre["NLEVELS_I"].value == 24


def num_layer_info(tre):
    num_layer_id = len(list(tre.find_all(r"LAYER_ID[0-9]{3}")))
    num_bitrate = len(list(tre.find_all(r"BITRATE[0-9]{3}")))
    assert num_layer_id == num_bitrate
    return num_layer_id


def test_repeating_layerinfo():
    tre = jbpy.tre_factory("J2KLRA")

    for n in (1, 8, 24, 999):
        tre["NLAYERS_O"].value = n
        tre.finalize()
        assert tre[tre.trel_rename].isvalid()
        assert num_layer_info(tre) == n

    # values aren't deleted if list is shortened
    tre["BITRATE024"].value = 24.8
    tre["NLAYERS_O"].value = 25
    assert tre["BITRATE024"].value == 24.8
