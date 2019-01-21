from typing import (
    NamedTuple,
    Tuple,
    TYPE_CHECKING,
)

if TYPE_CHECKING:
    from eth2.beacon.types.crosslink_committees import ShardCommittee  # noqa: F401


BlockCommitteesInfo = NamedTuple(
    'BlockCommitteesInfo',
    (
        ('proposer_index', int),
        ('proposer_shard', int),
        ('proposer_committee_size', int),
        ('crosslinks_committees', Tuple['ShardCommittee'])
    )
)
