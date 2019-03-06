from typing import (
    Iterable,
    NewType,
    Sequence,
)

from cytoolz import (
    iterate,
    partition,
    take,
)
from eth2.beacon._utils.hash import (
    hash_eth2,
)
from eth_typing import (
    Hash32,
)


MerkleTree = NewType("MerkleTree", Sequence[Sequence[Hash32]])
MerkleProof = NewType("MerkleProof", Sequence[Hash32])


def get_root(tree: MerkleTree) -> Hash32:
    """
    Get the root hash of a Merkle tree.
    """
    return tree[0][0]


def get_branch_indices(node_index: int, depth: int) -> Iterable[int]:
    """
    Get the indices of all ancestors up until the root for a node with a given depth.
    """
    return tuple(take(depth, iterate(lambda index: index // 2, node_index)))


def _calc_parent_hash(left_node: Hash32, right_node: Hash32) -> Hash32:
    """
    Calculate the parent hash of a node and its sibling.
    """
    return hash_eth2(left_node + right_node)


def _hash_layer(layer: Sequence[Hash32]) -> Iterable[Hash32]:
    """
    Calculate the layer on top of another one.
    """
    return tuple(
        _calc_parent_hash(left, right)
        for left, right in partition(2, layer)
    )
