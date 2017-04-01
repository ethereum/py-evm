from rlp.sedes import (
    Binary,
)


address = Binary.fixed_length(20, allow_empty=True)
hash32 = Binary.fixed_length(32)
trie_root = Binary.fixed_length(32, allow_empty=True)
