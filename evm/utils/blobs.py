from itertools import (
    chain,
)

from eth_utils import (
    keccak,
)

from evm.constants import (
    CHUNK_SIZE,
    COLLATION_SIZE,
)


def chunk_iterator(blob):
    if len(blob) % CHUNK_SIZE != 0:
        raise ValueError("Blob size is {} which is not a multiple of chunk size ({})".format(
            len(blob),
            CHUNK_SIZE,
        ))
    for chunk_start in range(0, len(blob), CHUNK_SIZE):
        yield blob[chunk_start:chunk_start + CHUNK_SIZE]


def calc_merkle_root(leaves):
    current_layer = (keccak(leaf) for leaf in leaves)
    next_layer = []

    # check that leaves is not empty
    try:
        first_element = next(current_layer)
    except StopIteration:
        raise ValueError("No leaves given")
    else:
        current_layer = chain([first_element], current_layer)

    while True:
        try:
            left = next(current_layer)
        except StopIteration:
            # if all nodes in the current layer are processed, go to the next one
            assert len(next_layer) >= 1
            current_layer = iter(next_layer)
            next_layer = []
            continue

        try:
            right = next(current_layer)
        except StopIteration:
            if len(next_layer) == 0:
                # current_layer consists of a single element only, so we have reached the root
                return left
            else:
                raise ValueError("Number of leaves must be a power of two")

        next_layer.append(keccak(left + right))


def calc_chunks_root(blob):
    # remove empty chunks at the right
    if len(blob) != COLLATION_SIZE:
        raise ValueError("Blob is {} instead of {} bytes in size".format(
            len(blob),
            COLLATION_SIZE
        ))

    chunks = chunk_iterator(blob)
    return calc_merkle_root(chunks)
