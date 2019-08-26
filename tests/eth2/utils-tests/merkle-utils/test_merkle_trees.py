from eth_utils import ValidationError
import pytest

from eth2._utils.hash import hash_eth2
from eth2._utils.merkle.normal import (
    calc_merkle_tree,
    get_merkle_proof,
    get_merkle_root,
    get_merkle_root_from_items,
    get_root,
    verify_merkle_proof,
)


@pytest.mark.parametrize(
    "leaves,tree",
    [
        ((b"single leaf",), ((hash_eth2(b"single leaf"),),)),
        (
            (b"left", b"right"),
            (
                (hash_eth2(hash_eth2(b"left") + hash_eth2(b"right")),),
                (hash_eth2(b"left"), hash_eth2(b"right")),
            ),
        ),
        (
            (b"1", b"2", b"3", b"4"),
            (
                (
                    hash_eth2(
                        hash_eth2(hash_eth2(b"1") + hash_eth2(b"2"))
                        + hash_eth2(hash_eth2(b"3") + hash_eth2(b"4"))
                    ),
                ),
                (
                    hash_eth2(hash_eth2(b"1") + hash_eth2(b"2")),
                    hash_eth2(hash_eth2(b"3") + hash_eth2(b"4")),
                ),
                (hash_eth2(b"1"), hash_eth2(b"2"), hash_eth2(b"3"), hash_eth2(b"4")),
            ),
        ),
    ],
)
def test_merkle_tree_calculation(leaves, tree):
    calculated_tree = calc_merkle_tree(leaves)
    assert calculated_tree == tree
    assert get_root(tree) == tree[0][0]
    assert get_merkle_root_from_items(leaves) == get_root(tree)


@pytest.mark.parametrize("leave_number", [0, 3, 5, 6, 7, 9])
def test_invalid_merkle_root_calculation(leave_number):
    with pytest.raises(ValueError):
        get_merkle_root_from_items((b"",) * leave_number)


@pytest.mark.parametrize(
    "leaves,index,proof",
    [
        ((b"1", b"2"), 0, (hash_eth2(b"2"),)),
        ((b"1", b"2"), 1, (hash_eth2(b"1"),)),
        (
            (b"1", b"2", b"3", b"4"),
            0,
            (hash_eth2(b"2"), hash_eth2(hash_eth2(b"3") + hash_eth2(b"4"))),
        ),
        (
            (b"1", b"2", b"3", b"4"),
            1,
            (hash_eth2(b"1"), hash_eth2(hash_eth2(b"3") + hash_eth2(b"4"))),
        ),
        (
            (b"1", b"2", b"3", b"4"),
            2,
            (hash_eth2(b"4"), hash_eth2(hash_eth2(b"1") + hash_eth2(b"2"))),
        ),
        (
            (b"1", b"2", b"3", b"4"),
            3,
            (hash_eth2(b"3"), hash_eth2(hash_eth2(b"1") + hash_eth2(b"2"))),
        ),
    ],
)
def test_merkle_proofs(leaves, index, proof):
    tree = calc_merkle_tree(leaves)
    root = get_root(tree)
    item = leaves[index]
    calculated_proof = get_merkle_proof(tree, index)
    assert calculated_proof == proof
    assert verify_merkle_proof(root, item, index, calculated_proof)

    assert not verify_merkle_proof(b"\x00" * 32, item, index, proof)
    assert not verify_merkle_proof(root, b"\x00" * 32, index, proof)
    assert not verify_merkle_proof(root, item, (index + 1) % len(leaves), proof)
    for replaced_index in range(len(proof)):
        altered_proof = (
            proof[:replaced_index] + (b"\x00" * 32,) + proof[replaced_index + 1 :]
        )
        assert not verify_merkle_proof(root, item, index, altered_proof)


def test_single_element_merkle_proof():
    leaves = (b"1",)
    tree = calc_merkle_tree(leaves)
    root = get_root(tree)
    assert get_merkle_proof(tree, 0) == ()
    assert verify_merkle_proof(root, b"1", 0, ())
    assert not verify_merkle_proof(b"\x00" * 32, b"1", 0, ())
    assert not verify_merkle_proof(root, b"2", 0, ())
    assert not verify_merkle_proof(root, b"1", 0, (b"\x00" * 32,))


@pytest.mark.parametrize("leaves", [(b"1",), (b"1", b"2"), (b"1", b"2", b"3", b"4")])
def test_proof_generation_index_validation(leaves):
    tree = calc_merkle_tree(leaves)
    for invalid_index in [-1, len(leaves)]:
        with pytest.raises(ValidationError):
            get_merkle_proof(tree, invalid_index)


def test_get_merkle_root():
    hash_0 = b"0" * 32
    leaves = (hash_0,)
    root = get_merkle_root(leaves)
    assert root == hash_0

    hash_1 = b"1" * 32
    leaves = (hash_0, hash_1)
    root = get_merkle_root(leaves)
    assert root == hash_eth2(hash_0 + hash_1)
