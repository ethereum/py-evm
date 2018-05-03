import functools
from typing import Dict, List, Tuple, Union

import rlp
from trie import (
    HexaryTrie,
)

from evm.constants import (
    BLANK_ROOT_HASH,
)
from evm.rlp.receipts import Receipt
from evm.rlp.transactions import BaseTransaction


def make_trie_root_and_nodes(
        items: Union[List[Receipt], List[BaseTransaction]]) -> Tuple[bytes, Dict[bytes, bytes]]:
    return _make_trie_root_and_nodes(tuple(rlp.encode(item) for item in items))


# This cache is expected to be useful when importing blocks as we call this once when importing
# and again when validating the imported block. But it should also help for post-Byzantium blocks
# as it's common for them to have duplicate receipt_roots. Given that, it probably makes sense to
# use a relatively small cache size here.
@functools.lru_cache(128)
def _make_trie_root_and_nodes(items: Tuple[bytes, ...]) -> Tuple[bytes, Dict[bytes, bytes]]:
    kv_store = {}  # type: Dict[bytes, bytes]
    trie = HexaryTrie(kv_store, BLANK_ROOT_HASH)
    with trie.squash_changes() as memory_trie:
        for index, item in enumerate(items):
            index_key = rlp.encode(index, sedes=rlp.sedes.big_endian_int)
            memory_trie[index_key] = item
    return trie.root_hash, kv_store
