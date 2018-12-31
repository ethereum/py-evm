from eth_typing import (
    Hash32,
)
import rlp

from eth.rlp.sedes import (
    uint64,
    hash32,
)

from eth.beacon.typing import (
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
        # Slot of the last justified beacon block
        ('justified_slot', uint64),
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
                 justified_slot: SlotNumber,
                 justified_block_root: Hash32) -> None:
        super().__init__(
            slot,
            shard,
            beacon_block_root,
            epoch_boundary_root,
            shard_block_root,
            latest_crosslink_root,
            justified_slot,
            justified_block_root,
        )
