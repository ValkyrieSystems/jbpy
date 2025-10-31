import jbpy


def assert_num_pts(tre):
    expected_ns = [f"{n + 1:04}" for n in range(tre["NUM_PTS"].value)]  # 1-indexed
    for prefix in ("PID", "LON", "LAT", "ZVL", "DIX", "DIY"):
        assert [
            x.name.removeprefix(prefix) for x in tre.find_all(rf"{prefix}[0-9]+")
        ] == expected_ns


def test_repeating_fields():
    tre = jbpy.tre_factory("REGPTB")

    for n in (1, 1298, 8, 24):
        tre["NUM_PTS"].value = n
        tre.finalize()
        assert tre[tre.trel_rename].isvalid()
        assert_num_pts(tre)

    # values aren't deleted if list is shortened
    tre["PID0024"].value = "dontdelete"
    tre["NUM_PTS"].value = 25
    assert tre["PID0024"].value == "dontdelete"
