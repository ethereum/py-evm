from eth2.beacon.types.shard_reassignment_records import (
    ShardReassignmentRecord,
)


def test_defaults(sample_shard_reassignment_record):
    shard_reassignment = ShardReassignmentRecord(**sample_shard_reassignment_record)
    assert shard_reassignment.validator_index == sample_shard_reassignment_record['validator_index']
    assert shard_reassignment.shard == sample_shard_reassignment_record['shard']
    assert shard_reassignment.slot == sample_shard_reassignment_record['slot']
