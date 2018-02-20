from eth_utils import (
    keccak,
)


class HashTrie(object):
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
