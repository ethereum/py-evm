import rlp

from eth.rlp.sedes import (
    uint24,
    uint64,
)
from eth.beacon.typing import (
    SlotNumber,
    ShardNumber,
    ValidatorIndex,
)


class ShardReassignmentRecord(rlp.Serializable):
    """
    Note: using RLP until we have standardized serialization format.
    """
    fields = [
        # Which validator to reassign
        ('validator_index', uint24),
        # To which shard
        ('shard', uint64),
        # When
        ('slot', uint64),
    ]

    def __init__(self,
                 validator_index: ValidatorIndex,
                 shard: ShardNumber,
                 slot: SlotNumber)-> None:
        super().__init__(
            validator_index=validator_index,
            shard=shard,
            slot=slot,
        )
