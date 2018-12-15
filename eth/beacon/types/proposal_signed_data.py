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
        # block root
        ('block_root', hash32),
    ]

    def __init__(self,
                 slot: int,
                 shard: int,
                 block_root: Hash32) -> None:
        super().__init__(
            slot,
            shard,
            block_root,
        )
