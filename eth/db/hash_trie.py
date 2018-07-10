from eth_hash.auto import keccak

from eth.db.keymap import (
    KeyMapDB,
)


class HashTrie(KeyMapDB):
    keymap = keccak
