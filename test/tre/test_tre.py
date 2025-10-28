import pytest

from jbpy.extensions import tre


def test_floatformat():
    conv = tre.FloatFormat("05.1f")
    cases = [
        (1.2, b"001.2"),
        (-1.2, b"-01.2"),
        (1234.2, b"1234.2"),
    ]
    for dv, ev in cases:
        assert conv.to_bytes(dv, 5) == ev
        assert conv.from_bytes(ev) == dv


@pytest.mark.parametrize("sz", (3, 4, 5))
def test_floatformat_sizereplacement(sz):
    conv = tre.FloatFormat("{size}.1f")
    ev = conv.to_bytes(0.1, sz)
    assert len(ev) == sz
    assert conv.from_bytes(ev) == 0.1


def test_flexiblefloat():
    conv = tre.FlexibleFloat()

    # all encodable in <=5 characters
    cases = [
        (-9999, b"-9999"),
        (-2.34, b"-2.34"),
        (-2.2, b"-2.20"),
        (-1, b"-0001"),
        (-0.0, b"00000"),
        (0, b"00000"),
        (0.0, b"00000"),
        (0.0001, b".0001"),
        (0.1, b".1000"),
        (1, b"00001"),
        (1.23, b"1.230"),
        (10000, b"10000"),
    ]
    for dv, ev in cases:
        assert conv.to_bytes(dv, 5) == ev
        assert conv.from_bytes(ev) == dv

    # rounding/truncation
    assert conv.to_bytes(54320.99999, 5) == b"54321"


def test_range_encodedfixedpoint_required():
    check = tre.EncodedFixedPoint("required", 2, 1)
    assert check.isvalid(b"+12.3")
    assert check.isvalid(b"-12.3")
    assert not check.isvalid(b" 12.3")
    assert not check.isvalid(b"+012.3")
    assert not check.isvalid(b"+12.30")
    assert not check.isvalid(b"+1234")
    assert not check.isvalid(b"000")


def test_range_encodedfixedpoint_unsigned():
    check = tre.EncodedFixedPoint("unsigned", 2, 1)
    assert check.isvalid(b"12.3")
    assert check.isvalid(b"00.0")
    assert not check.isvalid(b" 12.3")
    assert not check.isvalid(b"+12.3")
    assert not check.isvalid(b"012.3")
    assert not check.isvalid(b"12.30")
    assert not check.isvalid(b"000")
