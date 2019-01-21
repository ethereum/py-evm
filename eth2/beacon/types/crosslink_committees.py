from typing import (
    Sequence,
)

import rlp
from rlp.sedes import (
    CountableList,
)

from eth2.beacon.sedes import (
    uint24,
    uint64,
)
from eth2.beacon.typing import (
    ShardNumber,
    ValidatorIndex,
)


class CrosslinkCommittee(rlp.Serializable):
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
                 shard: ShardNumber,
                 committee: Sequence[ValidatorIndex],
                 total_validator_count: int)-> None:

        super().__init__(
            shard=shard,
            committee=committee,
            total_validator_count=total_validator_count,
        )
