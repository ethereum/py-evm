from eth_typing import (
    Hash32,
)
import rlp

from eth.rlp.sedes import (
    uint64,
    hash32,
)


class CrosslinkRecord(rlp.Serializable):
    """
    Note: using RLP until we have standardized serialization format.
    """
    fields = [
        # What dynasty the crosslink was submitted in
        ('dynasty', uint64),
        # slot during which crosslink was added
        ('slot', uint64),
        # The block hash
        ('hash', hash32),
    ]

    def __init__(self,
                 dynasty: int,
                 slot: int,
                 hash: Hash32) -> None:

        super().__init__(
            dynasty=dynasty,
            slot=slot,
            hash=hash,
        )
