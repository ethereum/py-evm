import pytest

from eth2._utils.hash import hash_eth2
from eth2._utils.merkle.sparse import (
    calc_merkle_tree,
    get_merkle_proof,
    get_root,
    verify_merkle_proof,
)


@pytest.mark.parametrize(
    "items,expected_root",
    [
        (
            (b"1",),
            b"p\xb1\xcf\x0ej\x9b{\xf3\x16\xb2\x0f~,l\x15\xdc\xd3\xcdJ?K\x05GD`~9\xfe\x1e\xae\xf82",
        ),
        (
            (b"1", b"2"),
            b"\x83H%\xac_\xbd\x03\xd7!\x95Z\x08\xa1\x0c\xe8/\x83\xfe\x8a\x9b\xe5fe\x94J\xd4\xf5\x1c&FE\xdd",  # noqa: E501
        ),
        (
            (b"1", b"2", b"3"),
            b'\xc2\x95\xf3\xf8:\xc1" \xf1\xe4\x87b_\xa4\xdb\xa9\x14e\xd3\xa9D\x85j\x17\xf5R\xc4\xdd\x88"\x8aJ',  # noqa: E501
        ),
        (
            (b"1", b"2", b"3", b"4"),
            b"\x81!\xeaI4\xfc4_\x15\x13b\xa7tT#i\x9fT5\x1fs\x83B\xbc\x9f\xeb\xa1\x9ekv\xc5g",
        ),
    ],
)
def test_merkle_root_and_proofs(items, expected_root):
    tree = calc_merkle_tree(items)
    assert get_root(tree) == expected_root
    for index in range(len(items)):
        item = items[index]
        proof = get_merkle_proof(tree, index)
        assert verify_merkle_proof(expected_root, hash_eth2(item), index, proof)

        assert not verify_merkle_proof(b"\x32" * 32, hash_eth2(item), index, proof)
        assert not verify_merkle_proof(
            expected_root, hash_eth2(b"\x32" * 32), index, proof
        )
        if len(items) > 1:
            assert not verify_merkle_proof(
                expected_root, hash_eth2(item), (index + 1) % len(items), proof
            )
        for replaced_index in range(len(proof)):
            altered_proof = (
                proof[:replaced_index] + (b"\x32" * 32,) + proof[replaced_index + 1 :]
            )
            assert not verify_merkle_proof(
                expected_root, hash_eth2(item), index, altered_proof
            )
