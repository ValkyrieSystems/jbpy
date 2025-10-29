import jbpy


def num_proj_params(tre):
    return len(list(tre.find_all(r"PRJ[1-9]")))


def test_repeating_proj_params():
    tre = jbpy.tre_factory("PRJPSB")

    for n in range(0, 10):
        tre["NUM_PRJ"].value = n
        tre.finalize()
        tre[tre.trel_rename].isvalid()
        assert num_proj_params(tre) == n

    # values aren't deleted if list is shortened
    tre["PRJ2"].value = 24.8
    tre["NUM_PRJ"].value = 2
    assert tre["PRJ2"].value == 24.8
