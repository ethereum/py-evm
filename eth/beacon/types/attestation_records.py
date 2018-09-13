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
    int16,
    int64,
    int256,
    hash32,
)


class AttestationRecord(rlp.Serializable):
    """
    Note: using RLP until we have standardized serialization format.
    """
    fields = [
        # Slot number
        ('slot', int64),
        # Shard ID
        ('shard_id', int16),
        # List of block hashes that this signature is signing over that
        # are NOT part of the current chain, in order of oldest to newest
        ('oblique_parent_hashes', CountableList(hash32)),
        # Block hash in the shard that we are attesting to
        ('shard_block_hash', hash32),
        # Who is participating
        ('attester_bitfield', binary),
        # Last justified block
        ('justified_slot', int64),
        ('justified_block_hash', hash32),
        # The actual signature
        ('aggregate_sig', CountableList(int256)),
    ]

    def __init__(self,
                 slot: int,
                 shard_id: int,
                 shard_block_hash: Hash32,
                 attester_bitfield: bytes,
                 justified_slot: int,
                 justified_block_hash: Hash32,
                 oblique_parent_hashes: Tuple[Hash32, ...]=None,
                 aggregate_sig: Iterable[int]=None) -> None:
        if oblique_parent_hashes is None:
            oblique_parent_hashes = ()
        if aggregate_sig is None:
            aggregate_sig = [0, 0]

        super().__init__(
            slot=slot,
            shard_id=shard_id,
            oblique_parent_hashes=oblique_parent_hashes,
            shard_block_hash=shard_block_hash,
            attester_bitfield=attester_bitfield,
            justified_slot=justified_slot,
            justified_block_hash=justified_block_hash,
            aggregate_sig=aggregate_sig,
        )
