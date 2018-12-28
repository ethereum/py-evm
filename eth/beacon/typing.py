from typing import NewType, Tuple

SlotNumber = NewType('SlotNumber', int)  # uint64
ShardNumber = NewType('ShardNumber', int)  # uint64
BLSPubkey = NewType('BLSPubkey', int)  # uint384
BLSSignature = NewType('BLSSignature', Tuple[int, int])  # Tuple[uint384, uint384]

Bitfield = NewType('Bitfield', bytes)  # uint64


ValidatorIndex = NewType('ValidatorIndex', int)  # uint24
CommitteeIndex = NewType('CommitteeIndex', int)


Ether = NewType('Ether', int)  # uint64
Gwei = NewType('Gwei', int)  # uint64

Timestamp = NewType('Timestamp', int)
Second = NewType('Second', int)
