from typing import (
    Sequence,
)

import rlp
from rlp.sedes import (
    CountableList,
)

from eth.rlp.sedes import (
    uint24,
    uint64,
)


class ShardAndCommittee(rlp.Serializable):
    """
    Note: using RLP until we have standardized serialization format.
    """
    fields = [
        # Shard number
        ('shard', uint64),
        # Validator indices
        ('committee', CountableList(uint24)),
    ]

    def __init__(self,
                 shard: int,
                 committee: Sequence[int])-> None:
        if committee is None:
            committee = ()

        super().__init__(
            shard=shard,
            committee=committee,
        )
