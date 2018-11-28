from eth_typing import (
    Hash32,
)
import rlp

from eth.rlp.sedes import (
    uint64,
    hash32,
)


class AttestationSignedData(rlp.Serializable):
    """
    Note: using RLP until we have standardized serialization format.
    """
    fields = [
        # Slot number
        ('slot', uint64),
        # Shard number
        ('shard', uint64),
        # Hash of the block we're signing
        ('block_hash', hash32),
        # Hash of the ancestor at the cycle boundary
        ('cycle_boundary_hash', hash32),
        # Shard block hash being attested to
        ('shard_block_hash', hash32),
        # Last crosslink hash
        ('last_crosslink_hash', hash32),
        # Slot of last justified beacon block
        ('justified_slot', uint64),
        # Hash of last justified beacon block
        ('justified_block_hash', hash32),
    ]

    def __init__(self,
                 slot: int,
                 shard: int,
                 block_hash: Hash32,
                 cycle_boundary_hash: Hash32,
                 shard_block_hash: Hash32,
                 last_crosslink_hash: Hash32,
                 justified_slot: int,
                 justified_block_hash: Hash32) -> None:
        super().__init__(
            slot=slot,
            shard=shard,
            block_hash=block_hash,
            cycle_boundary_hash=cycle_boundary_hash,
            shard_block_hash=shard_block_hash,
            last_crosslink_hash=last_crosslink_hash,
            justified_slot=justified_slot,
            justified_block_hash=justified_block_hash,
        )
