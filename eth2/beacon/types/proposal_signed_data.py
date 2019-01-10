from eth_typing import (
    Hash32,
)
import rlp

from eth.beacon._utils.hash import hash_eth2

from eth.rlp.sedes import (
    uint64,
    hash32,
)
from eth.beacon.typing import (
    SlotNumber,
    ShardNumber,
)


class ProposalSignedData(rlp.Serializable):
    """
    Note: using RLP until we have standardized serialization format.
    """
    fields = [
        # Slot number
        ('slot', uint64),
        # Shard number (or `2**64 - 1` for beacon chain)
        ('shard', uint64),
        # block root
        ('block_root', hash32),
    ]

    def __init__(self,
                 slot: SlotNumber,
                 shard: ShardNumber,
                 block_root: Hash32) -> None:
        super().__init__(
            slot,
            shard,
            block_root,
        )

    _hash = None

    @property
    def hash(self) -> Hash32:
        if self._hash is None:
            self._hash = hash_eth2(rlp.encode(self))
        return self._hash

    @property
    def root(self) -> Hash32:
        # Alias of `hash`.
        # Using flat hash, might change to SSZ tree hash.
        return self.hash
