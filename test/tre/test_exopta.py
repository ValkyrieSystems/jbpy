import jbpy


def test_exopta():
    tre = jbpy.tre_factory("EXOPTA")
    tre.finalize()

    # test special sentinel-value types
    # field -> (decoded_value, expect_valid)
    cases_by_field = {
        "SUN_EL": [
            (-90.1, False),
            (-90.0, True),
            (0, True),
            (90.0, True),
            (90.1, False),
            (999.8, False),
            (999.9, True),
        ],
        "SUN_AZ": [
            (-0.1, False),
            (0, True),
            (358.9, True),
            (359.0, True),
            (359.1, True),  # EXOPTA goes to 359.9, USEOOA only goes to 359.0
            (359.9, True),
            (360.0, False),
            (999.8, False),
            (999.9, True),
        ],
    }
    for field, cases in cases_by_field.items():
        for decoded_val, expect_valid in cases:
            tre[field].value = decoded_val
            assert tre[field].isvalid() == expect_valid
