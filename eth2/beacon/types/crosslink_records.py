from eth_typing import (
    Hash32,
)
import rlp

from eth.rlp.sedes import (
    uint64,
    hash32,
)

from eth.beacon.typing import SlotNumber


class CrosslinkRecord(rlp.Serializable):
    """
    Note: using RLP until we have standardized serialization format.
    """
    fields = [
        # Slot during which crosslink was added
        ('slot', uint64),
        # Shard chain block root
        ('shard_block_root', hash32),
    ]

    def __init__(self,
                 slot: SlotNumber,
                 shard_block_root: Hash32) -> None:

        super().__init__(
            slot=slot,
            shard_block_root=shard_block_root,
        )
