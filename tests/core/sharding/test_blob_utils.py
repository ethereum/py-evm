import pytest

from itertools import (
    zip_longest,
)

from eth.utils.blobs import (
    calc_chunk_root,
    calc_merkle_root,
    deserialize_blobs,
    iterate_chunks,
    serialize_blobs,
)
from eth.utils.padding import (
    zpad_right,
)

from eth.utils.padding import zpad_left
from eth.utils.numeric import int_to_big_endian

from eth.constants import (
    CHUNK_SIZE,
    COLLATION_SIZE,
    MAX_BLOB_SIZE
)
from eth.exceptions import (
    ValidationError,
)


BLOB_SERIALIZATION_TEST_DATA = [  # [(blobs, unpadded_body), ...]
    (
        [],   # no blobs
        b"",  # everything zero
    ),
    (
        [
            b"\x00",  # blob 1
        ],
        b"".join([
            # blob 1
            b"\x01",   # indicator length 1
            b"\x00",   # data chunk 1
        ]),
    ),
    (
        [
            b"\x01",  # blob 1
        ],
        b"".join([
            # blob 1
            b"\x01",   # indicator length 1
            b"\x01",   # data chunk 1
        ]),
    ),
    (
        [
            b"\xaa" * 31  # blob 1
        ],
        b"".join([
            # blob 1
            b"\x1f",       # indicator length 31
            b"\xaa" * 31,  # data chunk 1
        ]),
    ),
    (
        [
            b"\xaa" * 32,  # blob 1
        ],
        b"".join([
            # blob 1
            b"\x00",       # indicator non terminal
            b"\xaa" * 31,  # data chunk 1
            b"\x01",       # indicator length 1
            b"\xaa",       # data chunk 2
        ]),
    ),
    (
        [
            b"\xaa" * 20,  # blob 1
            b"\xbb" * 15,  # blob 2
        ],
        b"".join([
            # blob 1
            b"\x14",       # indicator length 20
            b"\xaa" * 20,  # data chunk 1
            b"\x00" * 11,  # padding to end of chunk
            # blob 2
            b"\x0f",       # indicator length 15
            b"\xbb" * 15,  # data chunk 2
        ])
    ),
    (
        [
            b"\xaa" * 70,  # blob 1
            b"\xbb" * 40,  # blob 2
        ],
        b"".join([
            # blob 1
            b"\x00",       # indicator non terminal
            b"\xaa" * 31,  # data chunk 1
            b"\x00",       # indicator non terminal
            b"\xaa" * 31,  # data chunk 2
            b"\x08",       # indicator length 8
            b"\xaa" * 8,   # data chunk 3
            b"\x00" * 23,  # padding to end of chunk
            # blob 2
            b"\x00",       # indicator non terminal
            b"\xbb" * 31,  # data chunk 4
            b"\x09",       # indicator non terminal
            b"\xbb" * 9,   # data chunk 5
        ])
    ),
    (
        [
            b"\xaa" * MAX_BLOB_SIZE,  # blob 1
        ],
        b"".join([
            b"\x00",  # indicator non terminal
            b"\xaa" * 31,
        ] * (COLLATION_SIZE // CHUNK_SIZE - 1) + [
            b"\x1f",
            b"\xaa" * 31,
        ])
    )
]

# By default, tests parametrized with above values have test ids which are too long to print (as
# they contain the test data). Therefore, the following ids should be specified explicitly
# instead:
BLOB_SERIALIZATION_TEST_IDS = [
    "BLOB_SERIALIZATION_TEST_DATA[{}]".format(i)
    for i, _ in enumerate(BLOB_SERIALIZATION_TEST_DATA)
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
    with pytest.raises(ValidationError):
        next(iterate_chunks(body))

    chunks = test_chunks
    body = b"".join(chunks)[:-2]
    with pytest.raises(ValidationError):
        next(iterate_chunks(body))

    chunks = test_chunks
    body = b"".join(chunks) + b"\x00"
    with pytest.raises(ValidationError):
        next(iterate_chunks(body))

    chunks = test_chunks + [b"\x00" * CHUNK_SIZE]
    body = b"".join(chunks)
    with pytest.raises(ValidationError):
        next(iterate_chunks(body))


def test_chunk_root_calculation():
    with pytest.raises(ValidationError):
        calc_chunk_root(b"\x00" * (COLLATION_SIZE - 1))
    with pytest.raises(ValidationError):
        calc_chunk_root(b"\x00" * (COLLATION_SIZE + 1))
    with pytest.raises(ValidationError):
        calc_chunk_root(b"\x00" * (COLLATION_SIZE - CHUNK_SIZE))
    with pytest.raises(ValidationError):
        calc_chunk_root(b"\x00" * (COLLATION_SIZE + CHUNK_SIZE))

    chunk_number = COLLATION_SIZE // CHUNK_SIZE
    chunks = [b"\x00" * CHUNK_SIZE] * chunk_number
    body = b"".join(chunks)

    assert calc_chunk_root(body) == calc_merkle_root(chunks)


@pytest.mark.parametrize(
    "blobs,unpadded_body",
    BLOB_SERIALIZATION_TEST_DATA,
    ids=BLOB_SERIALIZATION_TEST_IDS,
)
def test_blob_serialization(blobs, unpadded_body):
    assert serialize_blobs(blobs) == zpad_right(unpadded_body, COLLATION_SIZE)


@pytest.mark.parametrize(
    "blobs,unpadded_body",
    BLOB_SERIALIZATION_TEST_DATA,
    ids=BLOB_SERIALIZATION_TEST_IDS,
)
def test_blob_iteration(blobs, unpadded_body):
    body = zpad_right(unpadded_body, COLLATION_SIZE)
    deserialized_blobs = list(deserialize_blobs(body))
    assert deserialized_blobs == blobs


@pytest.mark.parametrize("blobs", [
    [b""],
    [b"\x00", b""],
    [b"\x00" * (MAX_BLOB_SIZE + 1)]
])
def test_blob_length_checks(blobs):
    with pytest.raises(ValidationError):
        serialize_blobs(blobs)
