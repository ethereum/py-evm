from typing import (
    NamedTuple,
    NewType,
)


Slot = NewType('Slot', int)  # uint64
Epoch = NewType('Epoch', int)  # uint64
Shard = NewType('Shard', int)  # uint64

Bitfield = NewType('Bitfield', bytes)  # uint64


ValidatorIndex = NewType('ValidatorIndex', int)  # uint64

Gwei = NewType('Gwei', int)  # uint64

Timestamp = NewType('Timestamp', int)
Second = NewType('Second', int)


class FromBlockParams(NamedTuple):
    slot: Slot = None


# defaults to emulate "zero types"
default_slot = Slot(0)
default_epoch = Epoch(0)
default_shard = Shard(0)
default_validator_index = ValidatorIndex(0)
default_gwei = Gwei(0)
default_timestamp = Timestamp(0)
default_second = Second(0)
default_bitfield = Bitfield(b'')
