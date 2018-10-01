from rlp.sedes import (
    BigEndianInt,
    Binary,
)

from eth.constants import (
    COLLATION_SIZE,
)


address = Binary.fixed_length(20, allow_empty=True)
collation_body = Binary.fixed_length(COLLATION_SIZE)
hash32 = Binary.fixed_length(32)
int16 = BigEndianInt(16)
int24 = BigEndianInt(24)
int32 = BigEndianInt(32)
int64 = BigEndianInt(64)
int128 = BigEndianInt(128)
int256 = BigEndianInt(256)
trie_root = Binary.fixed_length(32, allow_empty=True)
