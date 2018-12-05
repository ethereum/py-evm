from eth_typing import (
    Hash32,
)
import rlp

from eth.rlp.sedes import (
    uint64,
    hash32,
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
        # Block hash
        ('block_hash', hash32),
    ]

    def __init__(self,
                 slot: int,
                 shard: int,
                 block_hash: Hash32) -> None:
        super().__init__(
            slot=slot,
            shard=shard,
            block_hash=block_hash,
        )
