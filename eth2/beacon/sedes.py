from rlp.sedes import (
    BigEndianInt,
    Binary,
)


hash32 = Binary.fixed_length(32)
uint24 = BigEndianInt(24)
uint64 = BigEndianInt(64)
uint384 = BigEndianInt(384)
