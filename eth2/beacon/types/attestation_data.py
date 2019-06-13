from eth.constants import (
    ZERO_HASH32,
)

from eth_typing import (
    Hash32,
)

import ssz
from ssz.sedes import (
    uint64,
    bytes32,
)

from eth2.beacon.typing import (
    Epoch,
)
from eth2.beacon.types.crosslinks import Crosslink
from eth_utils import (
    humanize_hash,
)


class AttestationData(ssz.Serializable):

    fields = [
        # LMD GHOST vote
        ('beacon_block_root', bytes32),

        # FFG vote
        ('source_epoch', uint64),
        ('source_root', bytes32),
        ('target_epoch', uint64),
        ('target_root', bytes32),

        # Crosslink vote
        ('crosslink', Crosslink),
    ]

    def __init__(self,
                 beacon_block_root: Hash32=ZERO_HASH32,
                 source_epoch: Epoch=0,
                 source_root: Hash32=ZERO_HASH32,
                 target_epoch: Epoch=0,
                 target_root: Hash32=ZERO_HASH32,
                 crosslink: Crosslink=Crosslink()) -> None:
        super().__init__(
            beacon_block_root=beacon_block_root,
            source_epoch=source_epoch,
            source_root=source_root,
            target_epoch=target_epoch,
            target_root=target_root,
            crosslink=crosslink,
        )

    def __str__(self) -> str:
        return (
            f"LMD  slot={self.slot} root={humanize_hash(self.beacon_block_root)} | "
            f"FFG  epoch={self.source_epoch} "
            f"{humanize_hash(self.source_root)}<-{humanize_hash(self.target_root)} | "
            f"CL  shard={self.shard} {humanize_hash(self.previous_crosslink.root)}"
            f"<-{humanize_hash(self.crosslink_data_root)}"
        )
