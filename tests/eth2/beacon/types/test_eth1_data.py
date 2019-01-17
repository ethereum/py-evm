from eth2.beacon.types.eth1_data import (
    Eth1Data,
)


def test_defaults(sample_eth1_data_params):
    eth1_data = Eth1Data(
        **sample_eth1_data_params,
    )
    assert eth1_data.deposit_root == sample_eth1_data_params['deposit_root']
    assert eth1_data.block_hash == sample_eth1_data_params['block_hash']
