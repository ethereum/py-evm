from eth_typing import (
    Hash32,
)

import ssz
from ssz.sedes import (
    uint64,
    bytes32,
)

from eth2.beacon.typing import EpochNumber


class CrosslinkRecord(ssz.Serializable):

    fields = [
        # Epoch during which crosslink was added
        ('epoch', uint64),
        # Shard chain block root
        ('shard_block_root', bytes32),
    ]

    def __init__(self,
                 epoch: EpochNumber,
                 shard_block_root: Hash32) -> None:

        super().__init__(
            epoch=epoch,
            shard_block_root=shard_block_root,
        )
