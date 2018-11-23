from eth.beacon.types.shard_and_committees import (
    ShardAndCommittee,
)


def test_defaults(sample_shard_and_committee_params):
    shard_and_committee = ShardAndCommittee(**sample_shard_and_committee_params)
    assert shard_and_committee.shard == sample_shard_and_committee_params['shard']
    assert shard_and_committee.committee == sample_shard_and_committee_params['committee']
