from typing import (
    NamedTuple,
    NewType,
)


Slot = NewType('Slot', int)  # uint64
Epoch = NewType('Epoch', int)  # uint64
Shard = NewType('Shard', int)  # uint64

Bitfield = NewType('Bitfield', bytes)  # uint64


ValidatorIndex = NewType('ValidatorIndex', int)  # uint64
CommitteeIndex = NewType('CommitteeIndex', int)

Gwei = NewType('Gwei', int)  # uint64

Timestamp = NewType('Timestamp', int)
Second = NewType('Second', int)


class FromBlockParams(NamedTuple):
    slot: Slot = None
