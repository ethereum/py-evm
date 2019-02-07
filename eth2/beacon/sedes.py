from rlp.sedes import (
    BigEndianInt,
    Binary,
)


hash32 = Binary.fixed_length(32)
uint64 = BigEndianInt(64)
