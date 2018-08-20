"""Utilities for binary merkle trees.

Merkle trees are represented as sequences of layers, from root to leaves. The root layer contains
only a single element, the leaves as many as there are data items in the tree. The data itself is
not considered to be part of the tree.
"""

import math
from typing import (
    cast,
    Hashable,
    NewType,
    Sequence,
)

from cytoolz import (
    identity,
    iterate,
    partition,
    reduce,
    take,
)
from eth_hash.auto import (
    keccak,
)
from eth_typing import (
    Hash32,
)
from eth_utils import (
    ValidationError,
)


MerkleTree = NewType("MerkleTree", Sequence[Sequence[Hash32]])
MerkleProof = NewType("MerkleProof", Sequence[Hash32])


def get_root(tree: MerkleTree) -> Hash32:
    """Get the root hash of a Merkle tree."""
    return tree[0][0]


def get_branch_indices(node_index: int, depth: int) -> Sequence[int]:
    """Get the indices of all ancestors up until the root for a node with a given depth."""
    return tuple(take(depth, iterate(lambda index: index // 2, node_index)))


def get_merkle_proof(tree: MerkleTree, item_index: int) -> Sequence[Hash32]:
    """Read off the Merkle proof for an item from a Merkle tree."""
    if item_index < 0 or item_index >= len(tree[-1]):
        raise ValidationError("Item index out of range")

    # special case of tree consisting of only root
    if len(tree) == 1:
        return ()

    branch_indices = get_branch_indices(item_index, len(tree))
    proof_indices = [i ^ 1 for i in branch_indices][:-1]  # get sibling by flipping rightmost bit
    return tuple(
        layer[proof_index]
        for layer, proof_index
        in zip(reversed(tree), proof_indices)
    )


def _calc_parent_hash(left_node: Hash32, right_node: Hash32) -> Hash32:
    """Calculate the parent hash of a node and its sibling."""
    return keccak(left_node + right_node)


def verify_merkle_proof(root: Hash32,
                        item: Hashable,
                        item_index: int,
                        proof: MerkleProof) -> bool:
    """Verify a Merkle proof against a root hash."""
    leaf = keccak(item)
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


def _hash_layer(layer: Sequence[Hash32]) -> Sequence[Hash32]:
    """Calculate the layer on top of another one."""
    return tuple(_calc_parent_hash(left, right) for left, right in partition(2, layer))


def calc_merkle_tree(items: Sequence[Hashable]) -> MerkleTree:
    """Calculate the Merkle tree corresponding to a list of items."""
    if len(items) == 0:
        raise ValidationError("No items given")
    n_layers = math.log2(len(items)) + 1
    if not n_layers.is_integer():
        raise ValidationError("Item number is not a power of two")
    n_layers = int(n_layers)

    leaves = tuple(keccak(item) for item in items)
    tree = cast(MerkleTree, tuple(take(n_layers, iterate(_hash_layer, leaves)))[::-1])
    if len(tree[0]) != 1:
        raise Exception("Invariant: There must only be one root")

    return tree


def calc_merkle_root(items: Sequence[Hashable]) -> Hash32:
    """Calculate the Merkle root corresponding to a list of items."""
    return get_root(calc_merkle_tree(items))
