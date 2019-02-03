from eth_typing import (
    Hash32,
)
import rlp

from eth2.beacon.sedes import (
    uint64,
    hash32,
)

from eth2.beacon.typing import (
    EpochNumber,
    SlotNumber,
    ShardNumber,
)


class AttestationData(rlp.Serializable):
    """
    Note: using RLP until we have standardized serialization format.
    """
    fields = [
        # Slot number
        ('slot', uint64),
        # Shard number
        ('shard', uint64),
        # Hash of the signed beacon block
        ('beacon_block_root', hash32),
        # Hash of the ancestor at the epoch boundary
        ('epoch_boundary_root', hash32),
        # Shard block root being attested to
        ('shard_block_root', hash32),
        # Last crosslink hash
        ('latest_crosslink_root', hash32),
        # epoch of the last justified beacon block
        ('justified_epoch', uint64),
        # Hash of the last justified beacon block
        ('justified_block_root', hash32),
    ]

    def __init__(self,
                 slot: SlotNumber,
                 shard: ShardNumber,
                 beacon_block_root: Hash32,
                 epoch_boundary_root: Hash32,
                 shard_block_root: Hash32,
                 latest_crosslink_root: Hash32,
                 justified_epoch: EpochNumber,
                 justified_block_root: Hash32) -> None:
        super().__init__(
            slot,
            shard,
            beacon_block_root,
            epoch_boundary_root,
            shard_block_root,
            latest_crosslink_root,
            justified_epoch,
            justified_block_root,
        )
