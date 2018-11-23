from eth.beacon.types.crosslink_records import (
    CrosslinkRecord,
)


def test_defaults(sample_crosslink_record_params):
    crosslink = CrosslinkRecord(**sample_crosslink_record_params)
    assert crosslink.slot == sample_crosslink_record_params['slot']
    assert crosslink.shard_block_hash == sample_crosslink_record_params['shard_block_hash']
