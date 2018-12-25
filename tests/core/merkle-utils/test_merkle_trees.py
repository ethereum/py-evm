import pytest

from eth_utils import (
    ValidationError,
)

from eth.constants import (
    ZERO_HASH32,
)
from eth.beacon._utils.hash import (
    hash_eth2,
)

from eth._utils.merkle import (
    calc_merkle_root,
    calc_merkle_tree,
    get_root,
    get_merkle_proof,
    get_merkle_root,
    get_updated_merkle_accumulator,
    verify_merkle_proof,
)


@pytest.mark.parametrize("leaves,tree", [
    (
        (b"single leaf",),
        (
            (hash_eth2(b"single leaf"),),
        ),
    ),
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
                    hash_eth2(
                        hash_eth2(b"1") + hash_eth2(b"2")
                    ) + hash_eth2(
                        hash_eth2(b"3") + hash_eth2(b"4")
                    )
                ),
            ),
            (
                hash_eth2(
                    hash_eth2(b"1") + hash_eth2(b"2")
                ),
                hash_eth2(
                    hash_eth2(b"3") + hash_eth2(b"4")
                ),
            ),
            (
                hash_eth2(b"1"),
                hash_eth2(b"2"),
                hash_eth2(b"3"),
                hash_eth2(b"4"),
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
        (hash_eth2(b"2"),),
    ),
    (
        (b"1", b"2"),
        1,
        (hash_eth2(b"1"),),
    ),
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


def test_get_merkle_root():
    hash_0 = b"0" * 32
    leaves = (hash_0,)
    root = get_merkle_root(leaves)
    assert root == hash_0

    hash_1 = b"1" * 32
    leaves = (hash_0, hash_1)
    root = get_merkle_root(leaves)
    assert root == hash_eth2(hash_0 + hash_1)


def test_get_updated_merkle_accumulator_three_elements():
    # Initialize the accumulator
    accumulator = tuple(
        ZERO_HASH32
        for _ in range(8)
    )

    # Add element 1
    position = 0
    value_1 = b"a" * 32
    accumulator = get_updated_merkle_accumulator(
        accumulator,
        position,
        value_1,
    )
    assert accumulator[0] == value_1

    # Add element 2
    position = 1
    value_2 = b"b" * 32
    accumulator = get_updated_merkle_accumulator(
        accumulator,
        position,
        value_2,
    )
    assert accumulator[1] == hash_eth2(accumulator[0] + value_2)

    # Add element 3
    position = 2
    value_3 = b"c" * 32
    accumulator = get_updated_merkle_accumulator(
        accumulator,
        position,
        value_3,
    )
    assert accumulator[0] == value_3

    leaves = (value_1, value_2, value_3)
    assert accumulator[1] == get_merkle_root(leaves[0:2])
    assert accumulator[0] == get_merkle_root(leaves[2:3])


def test_get_updated_merkle_accumulator_spec_example():
    accumulator = tuple(
        ZERO_HASH32
        for _ in range(64)
    )

    leaves = tuple(
        i.to_bytes(32, 'big')
        for i in range(329)
    )

    for i in range(329):
        accumulator = get_updated_merkle_accumulator(
            accumulator,
            position=i,
            value=leaves[i],
        )

    # `len(leaves) = 329` (note: 333 = 256 + 64 + 8 + 1)
    assert accumulator[8] == get_merkle_root(leaves[0:256])
    assert accumulator[6] == get_merkle_root(leaves[256:320])
    assert accumulator[3] == get_merkle_root(leaves[320:328])
    assert accumulator[0] == get_merkle_root(leaves[328:329])
