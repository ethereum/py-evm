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
    Slot,
    Shard,
)
from eth2.beacon.types.crosslinks import Crosslink
from eth_utils import (
    humanize_hash,
)


class AttestationData(ssz.Serializable):

    fields = [
        # LMD GHOST vote
        ('slot', uint64),
        ('beacon_block_root', bytes32),

        # FFG vote
        ('source_epoch', uint64),
        ('source_root', bytes32),
        ('target_root', bytes32),

        # Crosslink vote
        ('shard', uint64),
        ('previous_crosslink', Crosslink),
        ('crosslink_data_root', bytes32),
    ]

    def __init__(self,
                 slot: Slot,
                 beacon_block_root: Hash32,
                 source_epoch: Epoch,
                 source_root: Hash32,
                 target_root: Hash32,
                 shard: Shard,
                 previous_crosslink: Crosslink,
                 crosslink_data_root: Hash32) -> None:
        super().__init__(
            slot=slot,
            beacon_block_root=beacon_block_root,
            source_epoch=source_epoch,
            source_root=source_root,
            target_root=target_root,
            shard=shard,
            previous_crosslink=previous_crosslink,
            crosslink_data_root=crosslink_data_root,
        )

    def __str__(self) -> str:
        return (
            f"LMD  slot={self.slot} root={humanize_hash(self.beacon_block_root)} | "
            f"FFG  epoch={self.source_epoch} "
            f"{humanize_hash(self.source_root)}<-{humanize_hash(self.target_root)} | "
            f"CL  shard={self.shard} {humanize_hash(self.previous_crosslink.root)}"
            f"<-{humanize_hash(self.crosslink_data_root)}"
        )
