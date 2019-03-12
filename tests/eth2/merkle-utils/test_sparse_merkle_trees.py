import pytest

from eth2._utils.merkle.sparse import (
    calc_merkle_tree,
    get_merkle_proof,
    get_root,
    verify_merkle_proof,
)
from eth2.beacon._utils.hash import (
    hash_eth2,
)


@pytest.mark.parametrize("items,expected_root", [
    (
        (b"1",),
        b'~\xf5\xf2\x0e\xd0\xdc6\x1d\xe7\xc9\x01\xcc\x8a\xb5\xb8A\x0c\xb52ee\xc6\xdeR]\xe9\xda\x0ev\xe4l\x94',  # noqa: E501
    ),
    (
        (b"1", b"2",),
        b'\xa9k\x1a\xedB\xd8\xc7\x89rI<\xd82\xeflXI\x02\xae\xfd\x88\x89\xe5\xa2\x13\xa5\xc0\x7f2\x1fwu',  # noqa: E501
    ),
    (
        (b"1", b"2", b"3",),
        b' \xcd\xec\xfe5\xca\xd5\xe8\xdc\xdbN\xcda\x9cZ\x91\x8eX\xa2>\xe2>\x99\xda\x8d+$\x02\xd6s\x17N',  # noqa: E501
    ),
    (
        (b"1", b"2", b"3", b"4"),
        b'\xb5(\xa7\xcb\x01z\x94v`j\xee\xc4\xa0sd\xb6\x8d"\x93d\x1a\xa8F\xa5b\xee\xdc\x90\t\x1f\x96\xd8',  # noqa: E501
    ),
])
def test_merkle_root_and_proofs(items, expected_root):
    tree = calc_merkle_tree(items)
    assert get_root(tree) == expected_root
    for index in range(len(items)):
        item = items[index]
        proof = get_merkle_proof(tree, index)
        assert verify_merkle_proof(expected_root, hash_eth2(item), index, proof)

        assert not verify_merkle_proof(b"\x32" * 32, hash_eth2(item), index, proof)
        assert not verify_merkle_proof(expected_root, hash_eth2(b"\x32" * 32), index, proof)
        if len(items) > 1:
            assert not verify_merkle_proof(
                expected_root,
                hash_eth2(item),
                (index + 1) % len(items),
                proof
            )
        for replaced_index in range(len(proof)):
            altered_proof = proof[:replaced_index] + (b"\x32" * 32,) + proof[replaced_index + 1:]
            assert not verify_merkle_proof(expected_root, hash_eth2(item), index, altered_proof)
