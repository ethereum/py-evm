"""Utilities for sparse binary merkle trees.

Merkle trees are represented as sequences of layers, from root to leaves. The root layer contains
only a single element, the leaves as many as there are data items in the tree. The data itself is
not considered to be part of the tree.
"""

from typing import (
    Sequence,
    Union,
    TYPE_CHECKING,
)

from eth_utils.toolz import (
    cons,
    iterate,
    take,
)
from eth2._utils.hash import (
    hash_eth2,
)
from eth2._utils.tuple import update_tuple_item
from eth_typing import (
    Hash32,
)

from .common import (  # noqa: F401
    _calc_parent_hash,
    _hash_layer,
    get_branch_indices,
    get_merkle_proof,
    get_root,
    MerkleTree,
    MerkleProof,
)

if TYPE_CHECKING:
    from typing import Tuple  # noqa: F401

TreeDepth = 32
EmptyNodeHashes = tuple(
    take(TreeDepth, iterate(lambda node_hash: hash_eth2(node_hash + node_hash), b'\x00' * 32))
)


def verify_merkle_proof(root: Hash32,
                        leaf: Hash32,
                        index: int,
                        proof: MerkleProof) -> bool:
    """
    Verify that the given ``item`` is on the merkle branch ``proof``
    starting with the given ``root``.
    """
    assert len(proof) == TreeDepth
    value = leaf
    for i in range(TreeDepth):
        if index // (2**i) % 2:
            value = hash_eth2(proof[i] + value)
        else:
            value = hash_eth2(value + proof[i])
    return value == root


def calc_merkle_tree(items: Sequence[Union[bytes, bytearray]]) -> MerkleTree:
    """
    Calculate the Merkle tree corresponding to a list of items.
    """
    leaves = tuple(hash_eth2(item) for item in items)
    return calc_merkle_tree_from_leaves(leaves)


def get_merkle_root_from_items(items: Sequence[Union[bytes, bytearray]]) -> Hash32:
    """
    Calculate the Merkle root corresponding to a list of items.
    """
    return get_root(calc_merkle_tree(items))


def calc_merkle_tree_from_leaves(leaves: Sequence[Hash32]) -> MerkleTree:
    if len(leaves) == 0:
        raise ValueError("No leaves given")
    tree: Tuple[Sequence[Hash32], ...] = (leaves,)
    for i in range(TreeDepth):
        if len(tree[0]) % 2 == 1:
            tree = update_tuple_item(
                tree,
                0,
                tuple(tree[0]) + (EmptyNodeHashes[i],),
            )
        tree = tuple(cons(_hash_layer(tree[0]), tree))
    return MerkleTree(tree)


def get_merkle_root(leaves: Sequence[Hash32]) -> Hash32:
    """
    Return the Merkle root of the given 32-byte hashes.
    """
    return get_root(calc_merkle_tree_from_leaves(leaves))
