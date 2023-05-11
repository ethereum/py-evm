import contextlib
from typing import (
    Iterator,
    cast,
)

from eth_hash.auto import (
    keccak,
)
from trie import (
    HexaryTrie,
)

from eth.db.keymap import (
    KeyMapDB,
)


class HashTrie(KeyMapDB):
    keymap = keccak  # type: ignore  # mypy doesn't like that keccak accepts bytearray

    @contextlib.contextmanager
    def squash_changes(self) -> Iterator["HashTrie"]:
        with cast(HexaryTrie, self._db).squash_changes() as memory_trie:
            yield type(self)(memory_trie)
