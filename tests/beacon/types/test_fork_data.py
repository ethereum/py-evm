from eth.beacon.types.fork_data import (
    ForkData,
)


def test_defaults(sample_fork_data_params):
    fork_data = ForkData(**sample_fork_data_params)
    assert fork_data.pre_fork_version == sample_fork_data_params['pre_fork_version']
    assert fork_data.post_fork_version == sample_fork_data_params['post_fork_version']
    assert fork_data.fork_slot == sample_fork_data_params['fork_slot']
