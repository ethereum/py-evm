import ssz

from eth2.beacon.types.voluntary_exits import VoluntaryExit


def test_defaults(sample_voluntary_exit_params):
    exit = VoluntaryExit(**sample_voluntary_exit_params)

    assert exit.signature[0] == sample_voluntary_exit_params["signature"][0]
    assert ssz.encode(exit)
