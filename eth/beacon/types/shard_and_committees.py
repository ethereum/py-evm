from typing import (
    Iterable,
)

import rlp
from rlp.sedes import (
    CountableList,
)

from eth.rlp.sedes import (
    uint16,
    uint24,
)


class ShardAndCommittee(rlp.Serializable):
    """
    Note: using RLP until we have standardized serialization format.
    """
    fields = [
        # Shard number
        ('shard', uint16),
        # Validator indices
        ('committee', CountableList(uint24)),
    ]

    def __init__(self,
                 shard: int,
                 committee: Iterable[int])-> None:
        if committee is None:
            committee = ()

        super().__init__(
            shard=shard,
            committee=committee,
        )
