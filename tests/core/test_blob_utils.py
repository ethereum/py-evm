import pytest

from itertools import (
    zip_longest,
)

from evm.utils.blobs import (
    calc_chunks_root,
    calc_merkle_root,
    chunk_iterator,
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


def test_chunk_iteration():
    chunk_number = COLLATION_SIZE // CHUNK_SIZE
    test_chunks = [zpad_left(int_to_big_endian(i), CHUNK_SIZE) for i in range(chunk_number)]

    chunks = test_chunks
    body = b"".join(chunks)
    for recovered, original in zip_longest(chunk_iterator(body), chunks, fillvalue=None):
        assert recovered is not None and original is not None
        assert recovered == original

    chunks = test_chunks[:-2]
    body = b"".join(chunks)
    for recovered, original in zip_longest(chunk_iterator(body), chunks, fillvalue=None):
        assert recovered is not None and original is not None
        assert recovered == original

    body = b"".join(test_chunks)[:-2]
    with pytest.raises(ValueError):
        next(chunk_iterator(body))


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


def test_chunks_root_calculation():
    with pytest.raises(ValueError):
        calc_chunks_root(b"\x00" * (COLLATION_SIZE - 1))
    with pytest.raises(ValueError):
        calc_chunks_root(b"\x00" * (COLLATION_SIZE + 1))
    with pytest.raises(ValueError):
        calc_chunks_root(b"\x00" * (COLLATION_SIZE - CHUNK_SIZE))
    with pytest.raises(ValueError):
        calc_chunks_root(b"\x00" * (COLLATION_SIZE + CHUNK_SIZE))

    chunk_number = COLLATION_SIZE // CHUNK_SIZE
    chunks = [b"\x00" * CHUNK_SIZE] * chunk_number
    body = b"".join(chunks)

    assert calc_chunks_root(body) == calc_merkle_root(chunks)
