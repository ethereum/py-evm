import pytest

from itertools import (
    zip_longest,
)

from evm.utils.blobs import (
    calc_chunk_root,
    calc_merkle_root,
    iterate_blobs,
    iterate_chunks,
    serialize_blobs,
)
from evm.utils.padding import (
    zpad_right,
)

from evm.utils.padding import zpad_left
from evm.utils.numeric import int_to_big_endian
from eth_utils import (
    keccak,
)

from evm.constants import (
    CHUNK_SIZE,
    COLLATION_SIZE,
)


BLOB_SERIALIZATION_TEST_DATA = [  # [(blobs, unpadded_body), ...]
    ([], b""),
    ([b"\x00"], b"\x01\x00"),
    ([b"\x01"], b"\x01\x01"),
    ([b"\xaa" * 31], b"\x1f" + b"\xaa" * 31),
    ([b"\xaa" * 32], b"\x00" + b"\xaa" * 31 + b"\x01" + b"\xaa"),
    (
        [b"\xaa" * 20, b"\xbb" * 15],
        b"\x14" + b"\xaa" * 20 + b"\x00" * 11 + b"\x0f" + b"\xbb" * 15
    ),
]


def test_chunk_iteration():
    chunk_number = COLLATION_SIZE // CHUNK_SIZE
    test_chunks = [zpad_left(int_to_big_endian(i), CHUNK_SIZE) for i in range(chunk_number)]

    chunks = test_chunks
    body = b"".join(chunks)
    for recovered, original in zip_longest(iterate_chunks(body), chunks, fillvalue=None):
        assert recovered is not None and original is not None
        assert recovered == original

    chunks = test_chunks[:-2]
    body = b"".join(chunks)
    for recovered, original in zip_longest(iterate_chunks(body), chunks, fillvalue=None):
        assert recovered is not None and original is not None
        assert recovered == original

    body = b"".join(test_chunks)[:-2]
    with pytest.raises(ValueError):
        next(iterate_chunks(body))


@pytest.mark.parametrize("leaves,root", [
    ([b"single leaf"], keccak(b"single leaf")),
    ([b"left", b"right"], keccak(keccak(b"left") + keccak(b"right"))),
    (
        [b"1", b"2", b"3", b"4"],
        keccak(
            keccak(
                keccak(b"1") + keccak(b"2")
            ) + keccak(
                keccak(b"3") + keccak(b"4")
            )
        )
    )
])
def test_merkle_root_calculation(leaves, root):
    assert calc_merkle_root(leaves) == root


@pytest.mark.parametrize("leave_number", [0, 3, 5, 6, 7, 9])
def test_invalid_merkle_root_calculation(leave_number):
    with pytest.raises(ValueError):
        calc_merkle_root([b""] * leave_number)


def test_chunk_root_calculation():
    with pytest.raises(ValueError):
        calc_chunk_root(b"\x00" * (COLLATION_SIZE - 1))
    with pytest.raises(ValueError):
        calc_chunk_root(b"\x00" * (COLLATION_SIZE + 1))
    with pytest.raises(ValueError):
        calc_chunk_root(b"\x00" * (COLLATION_SIZE - CHUNK_SIZE))
    with pytest.raises(ValueError):
        calc_chunk_root(b"\x00" * (COLLATION_SIZE + CHUNK_SIZE))

    chunk_number = COLLATION_SIZE // CHUNK_SIZE
    chunks = [b"\x00" * CHUNK_SIZE] * chunk_number
    body = b"".join(chunks)

    assert calc_chunk_root(body) == calc_merkle_root(chunks)


@pytest.mark.parametrize("blobs,unpadded_body", BLOB_SERIALIZATION_TEST_DATA)
def test_blob_serialization(blobs, unpadded_body):
    assert serialize_blobs(blobs) == zpad_right(unpadded_body, COLLATION_SIZE)


@pytest.mark.parametrize("blobs,unpadded_body", BLOB_SERIALIZATION_TEST_DATA)
def test_blob_iteration(blobs, unpadded_body):
    body = zpad_right(unpadded_body, COLLATION_SIZE)
    deserialized_blobs = list(iterate_blobs(body))
    assert deserialized_blobs == blobs


@pytest.mark.parametrize("blobs", [
    [b""],
    [b"\x00", b""],
    [b"\x00" * (31 * 2**((COLLATION_SIZE - 1).bit_length() - 5) + 1)]
])
def test_blob_length_checks(blobs):
    with pytest.raises(ValueError):
        serialize_blobs(blobs)
