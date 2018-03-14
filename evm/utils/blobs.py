import itertools
import math

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


def chunk_iterator(blob):
    # TODO: proper blob serialization when specification is out
    if len(blob) % CHUNK_SIZE != 0:
        raise ValueError("Blob size is {} which is not a multiple of chunk size ({})".format(
            len(blob),
            CHUNK_SIZE,
        ))
    for chunk_start in range(0, len(blob), CHUNK_SIZE):
        yield blob[chunk_start:chunk_start + CHUNK_SIZE]


def hash_layer(layer):
        for left, right in partition(2, layer):
            yield keccak(left + right)


def calc_merkle_root(leaves):
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


def calc_chunks_root(blob):
    if len(blob) != COLLATION_SIZE:
        raise ValueError("Blob is {} instead of {} bytes in size".format(
            len(blob),
            COLLATION_SIZE
        ))

    chunks = chunk_iterator(blob)
    return calc_merkle_root(chunks)
