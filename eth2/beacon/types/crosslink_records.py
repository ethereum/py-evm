from eth_typing import (
    Hash32,
)
import rlp

from eth2.beacon.sedes import (
    uint64,
    hash32,
)

from eth2.beacon.typing import EpochNumber


class CrosslinkRecord(rlp.Serializable):
    """
    Note: using RLP until we have standardized serialization format.
    """
    fields = [
        # Epoch during which crosslink was added
        ('epoch', uint64),
        # Shard chain block root
        ('shard_block_root', hash32),
    ]

    def __init__(self,
                 epoch: EpochNumber,
                 shard_block_root: Hash32) -> None:

        super().__init__(
            epoch=epoch,
            shard_block_root=shard_block_root,
        )
