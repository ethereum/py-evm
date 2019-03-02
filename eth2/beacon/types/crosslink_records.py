from eth_typing import (
    Hash32,
)

import ssz
from ssz.sedes import (
    uint64,
    bytes32,
)

from eth2.beacon._utils.hash import hash_eth2
from eth2.beacon.typing import Epoch


class CrosslinkRecord(ssz.Serializable):

    fields = [
        # Epoch during which crosslink was added
        ('epoch', uint64),
        # Shard chain block root
        ('crosslink_data_root', bytes32),
    ]

    def __init__(self,
                 epoch: Epoch,
                 crosslink_data_root: Hash32) -> None:

        super().__init__(
            epoch=epoch,
            crosslink_data_root=crosslink_data_root,
        )

    _hash = None

    @property
    def hash(self) -> Hash32:
        if self._hash is None:
            self._hash = hash_eth2(ssz.encode(self))
        return self._hash

    @property
    def root(self) -> Hash32:
        # Alias of `hash`.
        # Using flat hash, will likely use SSZ tree hash.
        return self.hash
