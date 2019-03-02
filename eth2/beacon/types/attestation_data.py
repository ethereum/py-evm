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
from eth2.beacon.types.crosslink_records import CrosslinkRecord


class AttestationData(ssz.Serializable):

    fields = [
        # Slot number
        ('slot', uint64),
        # Shard number
        ('shard', uint64),
        # Hash of the signed beacon block
        ('beacon_block_root', bytes32),
        # Hash of the ancestor at the epoch boundary
        ('epoch_boundary_root', bytes32),
        # Shard block root being attested to
        ('crosslink_data_root', bytes32),
        # Last crosslink hash
        ('latest_crosslink', CrosslinkRecord),
        # epoch of the last justified beacon block
        ('justified_epoch', uint64),
        # Hash of the last justified beacon block
        ('justified_block_root', bytes32),
    ]

    def __init__(self,
                 slot: Slot,
                 shard: Shard,
                 beacon_block_root: Hash32,
                 epoch_boundary_root: Hash32,
                 crosslink_data_root: Hash32,
                 latest_crosslink: CrosslinkRecord,
                 justified_epoch: Epoch,
                 justified_block_root: Hash32) -> None:
        super().__init__(
            slot,
            shard,
            beacon_block_root,
            epoch_boundary_root,
            crosslink_data_root,
            latest_crosslink,
            justified_epoch,
            justified_block_root,
        )
