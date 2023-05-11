from eth_hash.auto import (
    keccak,
)
from hypothesis import (
    given,
    strategies as st,
)
from trie import (
    HexaryTrie,
)

from eth.db.hash_trie import (
    HashTrie,
)


class ExplicitHashTrie:
    _trie = None

    def __init__(self, trie):
        self._trie = trie

    def __setitem__(self, key, value):
        self._trie[keccak(key)] = value

    def __getitem__(self, key):
        return self._trie[keccak(key)]

    def __delitem__(self, key):
        del self._trie[keccak(key)]

    def __contains__(self, key):
        return keccak(key) in self._trie

    @property
    def root_hash(self):
        return self._trie.root_hash

    @root_hash.setter
    def root_hash(self, value):
        self._trie.root_hash = value


@given(st.binary(), st.binary())
def test_keymap_equivalence(key, val):
    explicit_db = {}
    composed_db = {}

    explicit_trie = HexaryTrie(explicit_db)
    composed_trie = HexaryTrie(composed_db)

    explicit = ExplicitHashTrie(explicit_trie)
    composed = HashTrie(composed_trie)

    explicit[key] = val
    composed[key] = val

    assert explicit[key] == composed[key]
    assert explicit_db == composed_db
    assert explicit.root_hash == composed.root_hash

    explicit.root_hash = b"\0" * 32
    composed.root_hash = b"\0" * 32

    assert explicit_trie.root_hash == composed_trie.root_hash
