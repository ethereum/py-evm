from functools import partial

from eth_hash.auto import keccak

from evm.db.keymap import (
    KeyMapDB,
)


HashTrie = partial(KeyMapDB, keccak)
