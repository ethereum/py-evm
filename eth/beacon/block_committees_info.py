from typing import (
    Iterable,
    TYPE_CHECKING,
)

if TYPE_CHECKING:
    from eth.beacon.types.shard_and_committees import ShardAndCommittee  # noqa: F401


class BlockCommitteesInfo:
    _proposer_index = None  # validator index
    _proposer_index_in_committee = None
    _proposer_shard_id = None
    _proposer_committee_size = None
    _shards_and_committees = None

    def __init__(self,
                 proposer_index: int,
                 proposer_index_in_committee: int,
                 proposer_shard_id: int,
                 proposer_committee_size: int,
                 shards_and_committees: Iterable['ShardAndCommittee']) -> None:
        self._proposer_index = proposer_index
        self._proposer_index_in_committee = proposer_index_in_committee
        self._proposer_shard_id = proposer_shard_id
        self._proposer_committee_size = proposer_committee_size
        self._shards_and_committees = shards_and_committees

    @property
    def proposer_index(self) -> int:
        return self._proposer_index

    @property
    def proposer_index_in_committee(self) -> int:
        return self._proposer_index_in_committee

    @property
    def proposer_shard_id(self) -> int:
        return self._proposer_shard_id

    @property
    def proposer_committee_size(self) -> int:
        return self._proposer_committee_size

    @property
    def shards_and_committees(self) -> Iterable['ShardAndCommittee']:
        return self._shards_and_committees
