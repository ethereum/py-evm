from eth_typing import (
    BLSSignature,
    Hash32,
)

import ssz
from ssz.sedes import (
    bytes32,
    uint64,
    bytes96,
)

from eth2.beacon._utils.hash import hash_eth2

from eth2.beacon.constants import (
    EMPTY_SIGNATURE,
)
from eth2.beacon.typing import (
    Slot,
    Shard,
)


class Proposal(ssz.Serializable):

    fields = [
        # Slot number
        ('slot', uint64),
        # Shard number (`BEACON_CHAIN_SHARD_NUMBER` for beacon chain)
        ('shard', uint64),
        # Block root
        ('block_root', bytes32),
        # Signature
        ('signature', bytes96)
    ]

    def __init__(self,
                 slot: Slot,
                 shard: Shard,
                 block_root: Hash32,
                 signature: BLSSignature=EMPTY_SIGNATURE) -> None:
        super().__init__(
            slot,
            shard,
            block_root,
            signature,
        )

    _hash = None
    _signed_root = None

    @property
    def hash(self) -> Hash32:
        if self._hash is None:
            self._hash = hash_eth2(ssz.encode(self))
        return self._hash

    @property
    def root(self) -> Hash32:
        # Alias of `hash`.
        # Using flat hash, might change to SSZ tree hash.
        return self.hash

    @property
    def signed_root(self) -> Hash32:
        # Use SSZ built-in function
        if self._signed_root is None:
            self._signed_root = hash_eth2(ssz.encode(self.copy(signature=EMPTY_SIGNATURE)))
        return self._signed_root
