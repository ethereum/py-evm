import pytest

from eth_hash.auto import (
    keccak,
)

from eth.utils.merkle import (
    calc_merkle_root,
    calc_merkle_tree,
    get_root,
    get_merkle_proof,
    verify_merkle_proof,
)

from eth.exceptions import (
    ValidationError,
)


@pytest.mark.parametrize("leaves,tree", [
    (
        (b"single leaf",),
        (
            (keccak(b"single leaf"),),
        ),
    ),
    (
        (b"left", b"right"),
        (
            (keccak(keccak(b"left") + keccak(b"right")),),
            (keccak(b"left"), keccak(b"right")),
        ),
    ),
    (
        (b"1", b"2", b"3", b"4"),
        (
            (
                keccak(
                    keccak(
                        keccak(b"1") + keccak(b"2")
                    ) + keccak(
                        keccak(b"3") + keccak(b"4")
                    )
                ),
            ),
            (
                keccak(
                    keccak(b"1") + keccak(b"2")
                ),
                keccak(
                    keccak(b"3") + keccak(b"4")
                ),
            ),
            (
                keccak(b"1"),
                keccak(b"2"),
                keccak(b"3"),
                keccak(b"4"),
            ),
        ),
    ),
])
def test_merkle_tree_calculation(leaves, tree):
    calculated_tree = calc_merkle_tree(leaves)
    assert calculated_tree == tree
    assert get_root(tree) == tree[0][0]
    assert calc_merkle_root(leaves) == get_root(tree)


@pytest.mark.parametrize("leave_number", [0, 3, 5, 6, 7, 9])
def test_invalid_merkle_root_calculation(leave_number):
    with pytest.raises(ValidationError):
        calc_merkle_root((b"",) * leave_number)


@pytest.mark.parametrize("leaves,index,proof", [
    (
        (b"1", b"2"),
        0,
        (keccak(b"2"),),
    ),
    (
        (b"1", b"2"),
        1,
        (keccak(b"1"),),
    ),
    (
        (b"1", b"2", b"3", b"4"),
        0,
        (keccak(b"2"), keccak(keccak(b"3") + keccak(b"4"))),
    ),
    (
        (b"1", b"2", b"3", b"4"),
        1,
        (keccak(b"1"), keccak(keccak(b"3") + keccak(b"4"))),
    ),
    (
        (b"1", b"2", b"3", b"4"),
        2,
        (keccak(b"4"), keccak(keccak(b"1") + keccak(b"2"))),
    ),
    (
        (b"1", b"2", b"3", b"4"),
        3,
        (keccak(b"3"), keccak(keccak(b"1") + keccak(b"2"))),
    ),
])
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
        altered_proof = proof[:replaced_index] + (b"\x00" * 32,) + proof[replaced_index + 1:]
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


@pytest.mark.parametrize("leaves", [
    (b"1",),
    (b"1", b"2"),
    (b"1", b"2", b"3", b"4"),
])
def test_proof_generation_index_validation(leaves):
    tree = calc_merkle_tree(leaves)
    for invalid_index in [-1, len(leaves)]:
        with pytest.raises(ValidationError):
            get_merkle_proof(tree, invalid_index)
