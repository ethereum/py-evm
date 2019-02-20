from typing import (
    Tuple,
    NamedTuple,
)

from eth2.beacon.typing import (
    Shard,
    Slot,
    ValidatorIndex,
)


CommitteeAssignment = NamedTuple(
    'CommitteeAssignment',
    (
        ('committee', Tuple[ValidatorIndex, ...]),
        ('shard', Shard),
        ('slot', Slot),
        ('is_proposer', bool)
    )
)
