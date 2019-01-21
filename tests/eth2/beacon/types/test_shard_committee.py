from eth2.beacon.types.crosslink_committees import (
    CrosslinkCommittee,
)


def test_defaults(sample_crosslink_committee_params):
    crosslink_committee = CrosslinkCommittee(**sample_crosslink_committee_params)
    assert crosslink_committee.shard == sample_crosslink_committee_params['shard']
    assert crosslink_committee.committee == sample_crosslink_committee_params['committee']
    assert crosslink_committee.total_validator_count == sample_crosslink_committee_params['total_validator_count']  # noqa: E501
