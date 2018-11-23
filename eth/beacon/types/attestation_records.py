from typing import (
    Iterable,
    Tuple,
)

from eth_typing import (
    Hash32,
)
import rlp
from rlp.sedes import (
    binary,
    CountableList,
)

from eth.rlp.sedes import (
    uint16,
    uint64,
    uint256,
    hash32,
)


class AttestationRecord(rlp.Serializable):
    """
    Note: using RLP until we have standardized serialization format.
    """
    fields = [
        # Slot number
        ('slot', uint64),
        # Shard number
        ('shard', uint16),
        # Beacon block hashes not part of the current chain, oldest to newest
        ('parent_hashes', CountableList(hash32)),
        # Shard block hash being attested to
        ('shard_block_hash', hash32),
        # Last crosslink hash
        ('last_crosslink_hash', hash32),
        # Root of data between last hash and this one
        ('shard_block_combined_data_root', hash32),
        # Attester participation bitfield (1 bit per attester)
        ('attester_bitfield', binary),
        # Hash of last justified beacon block
        ('justified_slot', uint64),
        # Slot of last justified beacon block
        ('justified_block_hash', hash32),
        # BLS aggregate signature
        ('aggregate_sig', CountableList(uint256)),
    ]

    def __init__(self,
                 slot: int,
                 shard: int,
                 shard_block_hash: Hash32,
                 last_crosslink_hash: Hash32,
                 shard_block_combined_data_root: Hash32,
                 attester_bitfield: bytes,
                 justified_slot: int,
                 justified_block_hash: Hash32,
                 parent_hashes: Tuple[Hash32, ...]=None,
                 aggregate_sig: Iterable[int]=None) -> None:
        if parent_hashes is None:
            parent_hashes = ()
        if aggregate_sig is None:
            aggregate_sig = [0, 0]

        super().__init__(
            slot=slot,
            shard=shard,
            parent_hashes=parent_hashes,
            shard_block_hash=shard_block_hash,
            last_crosslink_hash=last_crosslink_hash,
            shard_block_combined_data_root=shard_block_combined_data_root,
            attester_bitfield=attester_bitfield,
            justified_slot=justified_slot,
            justified_block_hash=justified_block_hash,
            aggregate_sig=aggregate_sig,
        )
