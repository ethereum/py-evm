from typing import NewType, Tuple

SlotNumber = NewType('SlotNumber', int)  # uint64
ShardNumber = NewType('ShardNumber', int)  # uint64
BLSPubkey = NewType('BLSPubkey', int)  # uint384
BLSPubkeyAggregated = NewType('BLSPubkeyAggregated', int)  # uint384
BLSSignature = NewType('BLSSignature', bytes)
BLSSignatureAggregated = NewType(
    'BLSSignatureAggregated',
    Tuple[int, int]
)  # Tuple[uint384, uint384]
ValidatorIndex = NewType('ValidatorIndex', int)  # uint24
Bitfield = NewType('Bitfield', bytes)  # uint64

UnixTime = NewType('UnixTime', int)

Ether = NewType('Ether', int)  # uint64
Gwei = NewType('Gwei', int)  # uint64


Seconds = NewType('Seconds', int)
