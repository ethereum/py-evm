from typing import (
    Tuple,
    NamedTuple,
)

from eth2.beacon.typing import (
    ShardNumber,
    SlotNumber,
    ValidatorIndex,
)


CommitteeAssignment = NamedTuple(
    'CommitteeAssignment',
    (
        ('committee', Tuple[ValidatorIndex, ...]),
        ('shard', ShardNumber),
        ('slot', SlotNumber),
        ('is_proposer', bool)
    )
)
