from typing import (
    NamedTuple,
    Tuple,
    TYPE_CHECKING,
)

if TYPE_CHECKING:
    from eth.beacon.types.shard_committees import ShardCommittee  # noqa: F401


BlockCommitteesInfo = NamedTuple(
    'BlockCommitteesInfo',
    (
        ('proposer_index', int),
        ('proposer_index_in_committee', int),
        ('proposer_shard_id', int),
        ('proposer_committee_size', int),
        ('shards_committees', Tuple['ShardCommittee'])
    )
)
