from eth2.beacon.types.crosslinks import Crosslink


def test_defaults(sample_crosslink_record_params):
    crosslink = Crosslink(**sample_crosslink_record_params)
    assert crosslink.start_epoch == sample_crosslink_record_params["start_epoch"]
    assert crosslink.data_root == sample_crosslink_record_params["data_root"]
