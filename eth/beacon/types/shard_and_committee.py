from typing import (
    Iterable,
)

import rlp
from rlp.sedes import (
    CountableList,
)

from eth.rlp.sedes import (
    int16,
    int24,
)


class ShardAndCommittee(rlp.Serializable):
    """
    Note: using RLP until we have standardized serialization format.
    """
    fields = [
        # The shard ID
        ('shard_id', int16),
        # Validator indices
        ('committee', CountableList(int24)),
    ]

    def __init__(self,
                 shard_id: int,
                 committee: Iterable[int])-> None:
        if committee is None:
            committee = ()

        super().__init__(
            shard_id=shard_id,
            committee=committee,
        )
