from typing import (
    NamedTuple,
    NewType,
)


SlotNumber = NewType('SlotNumber', int)  # uint64
ShardNumber = NewType('ShardNumber', int)  # uint64
EpochNumber = NewType('EpochNumber', int)  # uint64
BLSPubkey = NewType('BLSPubkey', bytes)  # bytes48
BLSSignature = NewType('BLSSignature', bytes)  # bytes96

Bitfield = NewType('Bitfield', bytes)  # uint64


ValidatorIndex = NewType('ValidatorIndex', int)  # uint64
CommitteeIndex = NewType('CommitteeIndex', int)

Gwei = NewType('Gwei', int)  # uint64

Timestamp = NewType('Timestamp', int)
Second = NewType('Second', int)


class FromBlockParams(NamedTuple):
    slot: SlotNumber = None
