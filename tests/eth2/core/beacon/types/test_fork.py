import ssz

from eth2.beacon.types.forks import Fork


def test_defaults(sample_fork_params):
    fork = Fork(**sample_fork_params)
    assert fork.previous_version == sample_fork_params["previous_version"]
    assert fork.current_version == sample_fork_params["current_version"]
    assert fork.epoch == sample_fork_params["epoch"]
    assert ssz.encode(fork)
