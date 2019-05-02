from eth_typing import (
    Hash32,
)

import ssz
from ssz.sedes import (
    uint64,
    bytes32,
)

from eth2.beacon.typing import Epoch


class Crosslink(ssz.Serializable):

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
