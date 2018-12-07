from eth.beacon.types.shard_committees import (
    ShardCommittee,
)


def test_defaults(sample_shard_committee_params):
    shard_committee = ShardCommittee(**sample_shard_committee_params)
    assert shard_committee.shard == sample_shard_committee_params['shard']
    assert shard_committee.committee == sample_shard_committee_params['committee']
    assert shard_committee.total_validator_count == sample_shard_committee_params['total_validator_count']  # noqa: E501
