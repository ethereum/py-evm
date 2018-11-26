from typing import (
    Sequence,
)

from eth_typing import (
    Hash32,
)
import rlp
from rlp.sedes import (
    CountableList,
)

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
        # CYCLE_LENGTH parent hashes
        ('parent_hashes', CountableList(hash32)),
        # Shard block hash being attested to
        ('shard_block_hash', hash32),
        # Last crosslink hash
        ('last_crosslink_hash', hash32),
        # Root of data between last hash and this one
        ('shard_block_combined_data_root', hash32),
        # Hash of last justified beacon block
        ('justified_slot', uint64),
    ]

    def __init__(self,
                 slot: int,
                 shard: int,
                 shard_block_hash: Hash32,
                 last_crosslink_hash: Hash32,
                 shard_block_combined_data_root: Hash32,
                 justified_slot: int,
                 parent_hashes: Sequence[Hash32]=None) -> None:
        if parent_hashes is None:
            parent_hashes = ()

        super().__init__(
            slot=slot,
            shard=shard,
            parent_hashes=parent_hashes,
            shard_block_hash=shard_block_hash,
            last_crosslink_hash=last_crosslink_hash,
            shard_block_combined_data_root=shard_block_combined_data_root,
            justified_slot=justified_slot
        )
