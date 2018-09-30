import rlp

from eth.constants import (
    ZERO_HASH32,
)
from eth.rlp.sedes import (
    int64,
    hash32,
)


class CrosslinkRecord(rlp.Serializable):
    """
    Note: using RLP until we have standardized serialization format.
    """
    fields = [
        # What dynasty the crosslink was submitted in
        ('dynasty', int64),
        # slot during which crosslink was added
        ('slot', int64),
        # The block hash
        ('hash', hash32),
    ]

    def __init__(self,
                 dynasty=0,
                 slot=0,
                 hash=ZERO_HASH32):

        super().__init__(
            dynasty=dynasty,
            slot=slot,
            hash=hash,
        )
