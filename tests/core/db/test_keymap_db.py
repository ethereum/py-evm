import copy

from eth.db.backends.memory import (
    MemoryDB,
)
from eth.db.hash_trie import (
    HashTrie,
)


def test_keymap_db_can_be_copied_and_deep_copied():
    hash_trie = HashTrie(MemoryDB({b"a": b"1", b"b": b"2"}))

    copied_hash_trie = copy.copy(hash_trie)
    deep_copied_hash_trie = copy.deepcopy(hash_trie)

    assert hash_trie._db == copied_hash_trie._db
    assert hash_trie._db == deep_copied_hash_trie._db

    hash_trie[b"c"] = b"3"
    assert b"c" in hash_trie
    assert b"c" not in deep_copied_hash_trie
