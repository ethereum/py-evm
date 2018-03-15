import itertools
import math

from typing import (
    Iterable,
    Iterator,
)

from eth_utils import (
    keccak,
)

from evm.constants import (
    CHUNK_SIZE,
    COLLATION_SIZE,
)

from cytoolz import (
    partition,
    pipe,
)


def chunk_iterator(collation_body: bytes) -> Iterator[bytes]:
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


def calc_chunks_root(collation_body: bytes) -> bytes:
    if len(collation_body) != COLLATION_SIZE:
        raise ValueError("Blob is {} instead of {} bytes in size".format(
            len(collation_body),
            COLLATION_SIZE
        ))

    chunks = chunk_iterator(collation_body)
    return calc_merkle_root(chunks)
