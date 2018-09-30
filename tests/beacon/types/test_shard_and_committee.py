import pytest

from eth.beacon.types.shard_and_committee import (
    ShardAndCommittee,
)


@pytest.mark.parametrize(
    'param,default_value',
    [
        ('shard_id', 0),
        ('committee', ()),
    ]
)
def test_defaults(param, default_value, sample_shard_and_committee_params):
    del sample_shard_and_committee_params[param]
    shard_and_committee = ShardAndCommittee(**sample_shard_and_committee_params)

    assert getattr(shard_and_committee, param) == default_value
