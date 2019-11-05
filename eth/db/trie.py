import enum
import functools
from typing import cast, Dict, Tuple, Union, NamedTuple, List, Iterable

import rlp
from trie import (
    HexaryTrie,
)
from trie.constants import (
    BLANK_NODE_HASH,
    NODE_TYPE_BLANK,
    NODE_TYPE_BRANCH,
    NODE_TYPE_EXTENSION,
    NODE_TYPE_LEAF,
)
from trie.utils.nodes import (
    decode_node,
    extract_key,
    get_common_prefix_length,
    get_node_type,
)
from trie.utils.nibbles import nibbles_to_bytes


from eth_typing import Hash32
from eth_utils import to_tuple

from eth.constants import (
    BLANK_ROOT_HASH,
)
from eth.db.backends.base import BaseDB
from eth.rlp.receipts import Receipt
from eth.rlp.transactions import BaseTransaction

TransactionsOrReceipts = Union[Tuple[Receipt, ...], Tuple[BaseTransaction, ...]]
TrieRootAndData = Tuple[Hash32, Dict[Hash32, bytes]]


def make_trie_root_and_nodes(items: TransactionsOrReceipts) -> TrieRootAndData:
    return _make_trie_root_and_nodes(tuple(rlp.encode(item) for item in items))


# This cache is expected to be useful when importing blocks as we call this once when importing
# and again when validating the imported block. But it should also help for post-Byzantium blocks
# as it's common for them to have duplicate receipt_roots. Given that, it probably makes sense to
# use a relatively small cache size here.
@functools.lru_cache(128)
def _make_trie_root_and_nodes(items: Tuple[bytes, ...]) -> TrieRootAndData:
    kv_store: Dict[Hash32, bytes] = {}
    trie = HexaryTrie(kv_store, BLANK_ROOT_HASH)
    with trie.squash_changes() as memory_trie:
        for index, item in enumerate(items):
            index_key = rlp.encode(index, sedes=rlp.sedes.big_endian_int)
            memory_trie[index_key] = item
    return trie.root_hash, kv_store


### Copied over from lithp#trinity:lithp/firehose-protocol
### The best long-term home for this might be ethereum#py-trie?


Nibbles = Tuple[int, ...]


class NodeKind(enum.Enum):
    BLANK = NODE_TYPE_BLANK
    LEAF = NODE_TYPE_LEAF
    EXTENSION = NODE_TYPE_EXTENSION
    BRANCH = NODE_TYPE_BRANCH


class TrieNode(NamedTuple):
    kind: NodeKind
    rlp: bytes
    obj: List[bytes]  # this type is wrong but mypy doesn't support recursive types
    keccak: Hash32

    def __str__(self) -> str:
        if self.kind == NodeKind.EXTENSION:
            return (
                "TrieNode(Extension,"
                f" hash={self.keccak.hex()}"
                f" path={self.path_rest}"
                f" child={self.obj[1].hex()}"
                 ")"
            )
        if self.kind == NodeKind.LEAF:
            return (
                "TrieNode(Leaf,"
                f" hash={self.keccak.hex()}"
                f" path={self.path_rest[:10]}..."
                 ")"
            )
        return f"TrieNode(kind={self.kind.name} hash={self.keccak.hex()})"

    @property
    def path_rest(self) -> Nibbles:
        # careful: this doesn't make any sense for branches
        return cast(Nibbles, extract_key(self.obj))


def is_subtree(prefix: Nibbles, nibbles: Nibbles) -> bool:
    """
    Returns True if {nibbles} represents a subtree of {prefix}.
    """
    if len(nibbles) < len(prefix):
        # nibbles represents a bigger tree than prefix does
        return False
    return get_common_prefix_length(prefix, nibbles) == len(prefix)


@to_tuple
def _get_children_with_nibbles(node: TrieNode, prefix: Nibbles) -> Iterable[Tuple[Nibbles, Hash32]]:
    """
    Return the children of the given node at the given path, including their full paths
    """
    if node.kind == NodeKind.BLANK:
        return
    elif node.kind == NodeKind.LEAF:
        full_path = prefix + node.path_rest
        yield (full_path, cast(Hash32, node.obj[1]))
    elif node.kind == NodeKind.EXTENSION:
        full_path = prefix + node.path_rest
        # TODO: this cast to a Hash32 is not right, nodes smaller than 32 are inlined
        yield (full_path, cast(Hash32, node.obj[1]))
    elif node.kind == NodeKind.BRANCH:
        for i in range(17):
            full_path = prefix + (i,)
            yield (full_path, cast(Hash32, node.obj[i]))


def _get_node(db: BaseDB, node_hash: Hash32) -> TrieNode:
    if len(node_hash) < 32:
        node_rlp = node_hash
    else:
        node_rlp = db.get(node_hash)

    node = decode_node(node_rlp)
    node_type = get_node_type(node)

    return TrieNode(kind=NodeKind(node_type), rlp=node_rlp, obj=node, keccak=node_hash)


def _iterate_trie(db: BaseDB,
                  node: TrieNode,  # the node we should look at
                  sub_trie: Nibbles,  # which sub_trie to return nodes from
                  prefix: Nibbles,  # our current path in the trie
                  ) -> Iterable[Tuple[Nibbles, TrieNode]]:

    if node.kind == NodeKind.BLANK:
        return

    if node.kind == NodeKind.LEAF:
        full_path = prefix + node.path_rest

        if is_subtree(sub_trie, prefix) or is_subtree(sub_trie, full_path):
            # also check full_path because either the node or the item the node points to
            # might be part of the desired subtree
            yield (prefix, node)

        # there's no need to recur, this is a leaf
        return

    child_of_sub_trie = is_subtree(sub_trie, prefix)

    if child_of_sub_trie:
        # this node is part of the subtrie which should be returned
        yield (prefix, node)

    parent_of_sub_trie = is_subtree(prefix, sub_trie)

    if child_of_sub_trie or parent_of_sub_trie:
        for path, child_hash in _get_children_with_nibbles(node, prefix):
            child_node = _get_node(db, child_hash)
            yield from _iterate_trie(db, child_node, sub_trie, path)


def iterate_trie(db: BaseDB, root_hash: Hash32,
                 sub_trie: Nibbles = ()) -> Iterable[Tuple[Nibbles, TrieNode]]:

    if root_hash == BLANK_NODE_HASH:
        return

    root_node = _get_node(db, root_hash)

    yield from _iterate_trie(
        db, root_node, sub_trie,
        prefix=(),
    )


def iterate_leaves(db: BaseDB, root_hash: Hash32,
                   sub_trie: Nibbles = ()) -> Iterable[Tuple[Nibbles, bytes]]:
    "This returns all of the leaves in the trie, along with their full paths"

    node_iterator = iterate_trie(db, root_hash, sub_trie)

    for path, node in node_iterator:
        if node.kind == NodeKind.LEAF:
            full_path = nibbles_to_bytes(path + node.path_rest)
            yield (full_path, node.obj[1])
