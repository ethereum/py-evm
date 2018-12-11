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


class ShardCommittee(rlp.Serializable):
    """
    Note: using RLP until we have standardized serialization format.
    """
    fields = [
        # Shard number
        ('shard', uint64),
        # Validator indices
        ('committee', CountableList(uint24)),
        # Total validator count (for proofs of custody)
        ('total_validator_count', uint64),
    ]

    def __init__(self,
                 shard: int,
                 committee: Sequence[int],
                 total_validator_count: int)-> None:

        super().__init__(
            shard=shard,
            committee=committee,
            total_validator_count=total_validator_count,
        )
