from eth_typing import (
    Hash32,
)

import ssz
from ssz.sedes import (
    uint64,
    bytes32,
)

from eth2.beacon.typing import Epoch
from eth_utils import (
    encode_hex,
    humanize_hash,
)


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

    def __str__(self) -> str:
        return f"CL:{self.epoch} data_root={humanize_hash(self.crosslink_data_root)}"

    def __repr__(self) -> str:
        return f"<Crosslink epoch={self.epoch} data_root={encode_hex(self.crosslink_data_root)}>"
