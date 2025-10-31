import logging

import pytest

import jbpy
import jbpy.extensions.tre.RPC00B


def test_scientific_notation_fields():
    tre = jbpy.tre_factory("RPC00B")
    tre.finalize()

    cases = [
        (0.123456, b"+1.234560E-1"),
        (1.234567e1, b"+1.234567E+1"),
        (1.234567e2, b"+1.234567E+2"),
        (-1.234567e-3, b"-1.234567E-3"),
        (-1.234567e-4, b"-1.234567E-4"),
        (1234567, b"+1.234567E+6"),
        (1e-15, b"+0.000001E-9"),
    ]
    for dv, ev in cases:
        tre["LINE_NUM_COEFF_1"].value = dv
        assert tre["LINE_NUM_COEFF_1"].encoded_value == ev
        assert tre["LINE_NUM_COEFF_1"].isvalid()
        tre["LINE_NUM_COEFF_1"].encoded_value = ev
        assert tre["LINE_NUM_COEFF_1"].value == dv
        assert tre["LINE_NUM_COEFF_1"].isvalid()


def test_sci_float(caplog):
    def assert_to_bytes(args, dv, ev):
        assert jbpy.extensions.tre.RPC00B.SciFloat(*args).to_bytes(dv, len(ev)) == ev

    assert_to_bytes(("unsigned", 3, 1), 1.0, b"1.000E+0")
    assert_to_bytes(("unsigned", 4, 1), 1.0, b"1.0000E+0")
    assert_to_bytes(("unsigned", 4, 2), 1.0, b"1.0000E+00")

    assert_to_bytes(("required", 3, 1), 1.0, b"+1.000E+0")
    assert_to_bytes(("required", 4, 1), 1.0, b"+1.0000E+0")
    assert_to_bytes(("required", 4, 2), 1.0, b"+1.0000E+00")

    with pytest.raises(ValueError, match="converter is unsigned"):
        assert_to_bytes(("unsigned", 3, 1), -1.0, b"X.XXXE+X")
    assert_to_bytes(("required", 3, 1), -1.0, b"-1.000E+0")

    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="jbpy.extensions.tre.RPC00B"):
        assert_to_bytes(("unsigned", 4, 2), 1.0e100, b"9.9999E+99")
        assert len(caplog.records) == 1
        assert "does not fit in field. Rounding" in caplog.records[0].message
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="jbpy.extensions.tre.RPC00B"):
        assert_to_bytes(("required", 4, 2), -1.0e100, b"-9.9999E+99")
        assert len(caplog.records) == 1
        assert "does not fit in field. Rounding" in caplog.records[0].message
    assert_to_bytes(("unsigned", 4, 3), 1.0e100, b"1.0000E+100")

    assert_to_bytes(("unsigned", 2, 1), 1.0e-11, b"0.01E-9")
    assert_to_bytes(("unsigned", 2, 2), 1.0e-11, b"1.00E-11")
    assert_to_bytes(("required", 2, 1), -1.0e-12, b"-0.00E+0")
    assert_to_bytes(("required", 2, 2), -1.0e-12, b"-1.00E-12")
    assert_to_bytes(("unsigned", 2, 1), 9.99999999e9, b"9.99E+9")
    assert_to_bytes(("required", 2, 1), -9.99999999e9, b"-9.99E+9")
