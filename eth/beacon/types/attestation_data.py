from eth_typing import (
    Hash32,
)
import rlp

from eth.rlp.sedes import (
    uint64,
    hash32,
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
        ('beacon_block_hash', hash32),
        # Hash of the ancestor at the epoch boundary
        ('epoch_boundary_hash', hash32),
        # Shard block hash being attested to
        ('shard_block_hash', hash32),
        # Last crosslink hash
        ('latest_crosslink_hash', hash32),
        # Slot of the last justified beacon block
        ('justified_slot', uint64),
        # Hash of the last justified beacon block
        ('justified_block_hash', hash32),
    ]

    def __init__(self,
                 slot: int,
                 shard: int,
                 beacon_block_hash: Hash32,
                 epoch_boundary_hash: Hash32,
                 shard_block_hash: Hash32,
                 latest_crosslink_hash: Hash32,
                 justified_slot: int,
                 justified_block_hash: Hash32) -> None:
        super().__init__(
            slot=slot,
            shard=shard,
            beacon_block_hash=beacon_block_hash,
            epoch_boundary_hash=epoch_boundary_hash,
            shard_block_hash=shard_block_hash,
            latest_crosslink_hash=latest_crosslink_hash,
            justified_slot=justified_slot,
            justified_block_hash=justified_block_hash,
        )
