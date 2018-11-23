from eth_typing import (
    Hash32,
)
import rlp

from eth.rlp.sedes import (
    uint64,
    hash32,
)


class CrosslinkRecord(rlp.Serializable):
    """
    Note: using RLP until we have standardized serialization format.
    """
    fields = [
        # Slot during which crosslink was added
        ('slot', uint64),
        # Shard chain block hash
        ('shard_block_hash', hash32),
    ]

    def __init__(self,
                 slot: int,
                 shard_block_hash: Hash32) -> None:

        super().__init__(
            slot=slot,
            shard_block_hash=shard_block_hash,
        )
