"""Utilities for binary merkle trees.

Merkle trees are represented as sequences of layers, from root to leaves. The root layer contains
only a single element, the leaves as many as there are data items in the tree. The data itself is
not considered to be part of the tree.
"""

import math
from typing import (
    Sequence,
    Union,
)

from cytoolz import (
    identity,
    iterate,
    reduce,
    take,
)

from eth_typing import (
    Hash32,
)

from eth2._utils.hash import (
    hash_eth2,
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


def verify_merkle_proof(root: Hash32,
                        item: Union[bytes, bytearray],
                        item_index: int,
                        proof: MerkleProof) -> bool:
    """
    Verify a Merkle proof against a root hash.
    """
    leaf = hash_eth2(item)
    branch_indices = get_branch_indices(item_index, len(proof))
    node_orderers = [
        identity if branch_index % 2 == 0 else reversed
        for branch_index in branch_indices
    ]
    proof_root = reduce(
        lambda n1, n2_and_order: _calc_parent_hash(*n2_and_order[1]([n1, n2_and_order[0]])),
        zip(proof, node_orderers),
        leaf,
    )
    return proof_root == root


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
    n_layers = math.log2(len(leaves)) + 1
    if not n_layers.is_integer():
        raise ValueError("Number of leaves is not a power of two")
    n_layers = int(n_layers)

    reversed_tree = tuple(take(n_layers, iterate(_hash_layer, leaves)))
    tree = MerkleTree(tuple(reversed(reversed_tree)))

    if len(tree[0]) != 1:
        raise Exception("Invariant: There must only be one root")

    return tree


def get_merkle_root(leaves: Sequence[Hash32]) -> Hash32:
    """
    Return the Merkle root of the given 32-byte hashes.
    Note: it has to be a full tree, i.e., `len(values)` is an exact power of 2.
    """
    return get_root(calc_merkle_tree_from_leaves(leaves))
