from eth_typing import (
    Hash32,
)

import ssz
from ssz.sedes import (
    bytes32,
    uint64,
)

from eth2.beacon._utils.hash import hash_eth2

from eth2.beacon.typing import (
    SlotNumber,
    ShardNumber,
)


class ProposalSignedData(ssz.Serializable):

    fields = [
        # Slot number
        ('slot', uint64),
        # Shard number (or `2**64 - 1` for beacon chain)
        ('shard', uint64),
        # block root
        ('block_root', bytes32),
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
