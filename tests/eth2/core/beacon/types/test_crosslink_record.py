from eth2.beacon.types.crosslinks import (
    Crosslink,
)


def test_defaults(sample_crosslink_record_params):
    crosslink = Crosslink(**sample_crosslink_record_params)
    assert crosslink.epoch == sample_crosslink_record_params['epoch']
    assert crosslink.crosslink_data_root == sample_crosslink_record_params['crosslink_data_root']
