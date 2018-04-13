import itertools
import math

from typing import (
    Iterable,
    Iterator,
)

from eth_utils import (
    apply_to_return_value,
    int_to_big_endian,
    keccak,
)
from evm.utils.padding import (
    zpad_right,
)

from evm.constants import (
    CHUNK_SIZE,
    COLLATION_SIZE,
)

from cytoolz import (
    partition,
    pipe,
)


def iterate_chunks(collation_body: bytes) -> Iterator[bytes]:
    if len(collation_body) % CHUNK_SIZE != 0:
        raise ValueError("Blob size is {} which is not a multiple of chunk size ({})".format(
            len(collation_body),
            CHUNK_SIZE,
        ))
    for chunk_start in range(0, len(collation_body), CHUNK_SIZE):
        yield collation_body[chunk_start:chunk_start + CHUNK_SIZE]


def hash_layer(layer: Iterable[bytes]) -> Iterator[bytes]:
    for left, right in partition(2, layer):
        yield keccak(left + right)


def calc_merkle_root(leaves: Iterable[bytes]) -> bytes:
    leaves = list(leaves)  # convert potential iterator to list
    if len(leaves) == 0:
        raise ValueError("No leaves given")

    n_layers = math.log2(len(leaves))
    if not n_layers.is_integer():
        raise ValueError("Leave number is not a power of two")
    n_layers = int(n_layers)

    first_layer = (keccak(leaf) for leaf in leaves)

    root, *extras = pipe(first_layer, *itertools.repeat(hash_layer, n_layers))
    assert not extras, "Invariant: should only be a single value"
    return root


def calc_chunk_root(collation_body: bytes) -> bytes:
    if len(collation_body) != COLLATION_SIZE:
        raise ValueError("Blob is {} instead of {} bytes in size".format(
            len(collation_body),
            COLLATION_SIZE
        ))

    chunks = iterate_chunks(collation_body)
    return calc_merkle_root(chunks)


def check_body_size(body):
    if len(body) > COLLATION_SIZE:
        raise ValueError("Collation body exceeds maximum allowed size")
    return body


@apply_to_return_value(check_body_size)
@apply_to_return_value(lambda v: zpad_right(v, COLLATION_SIZE))
@apply_to_return_value(b"".join)
def serialize_blobs(blobs: Iterable[bytes]) -> bytes:
    """Serialize a sequence of blobs and return a collation body."""
    for blob in blobs:
        if len(blob) == 0:
            raise ValueError("Cannot serialize blob of length 0")
        if len(blob) > 31 * 2**((COLLATION_SIZE - 1).bit_length() - 5):
            raise ValueError("Cannot serialize blob of size {}".format(len(blob)))

        blob_index = 0
        for blob_index in range(0, len(blob), 31):
            remaining_blob_bytes = len(blob) - blob_index

            if remaining_blob_bytes <= 31:
                length_bits = remaining_blob_bytes
            else:
                length_bits = 0

            flag_bits = 0  # TODO: second parameter? blobs as tuple `(flags, blobs)`?
            indicator_byte = int_to_big_endian(length_bits | flag_bits * 0b00100000)
            assert len(indicator_byte) == 1

            yield indicator_byte
            yield blob[blob_index:blob_index + 31]

        chunk_filler = b"\x00" * (31 - (len(blob) - blob_index))
        yield chunk_filler


def iterate_blobs(body: bytes) -> Iterator[bytes]:
    """Iterate over the blobs encoded in a body."""
    blob = b""
    for chunk in iterate_chunks(body):
        indicator_byte = chunk[0]
        flag_bits = indicator_byte & 0b11100000  # TODO: yield, filter, ...?  # noqa: F841
        length_bits = indicator_byte & 0b00011111

        if length_bits == 0:
            length = 31
            terminal = False
        else:
            length = length_bits
            terminal = True

        blob += chunk[1:length + 1]
        if terminal:
            yield blob
            blob = b""
