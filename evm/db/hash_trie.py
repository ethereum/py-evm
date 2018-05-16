from eth_hash.auto import keccak

from evm.db.keymap import (
    KeyMapDB,
)


class HashTrie(KeyMapDB):
    keymap = keccak
