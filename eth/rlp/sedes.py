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
uint24 = BigEndianInt(24)
uint32 = BigEndianInt(32)
uint64 = BigEndianInt(64)
uint256 = BigEndianInt(256)
trie_root = Binary.fixed_length(32, allow_empty=True)
