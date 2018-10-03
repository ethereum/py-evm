
from typing import (
    Any,
    Iterable,
    Sequence,
    TypeVar,
)

from eth_typing import (
    Hash32,
)
from eth_utils import (
    to_tuple,
)

from eth.utils.blake import (
    blake,
)


TItem = TypeVar('TItem')


def shuffle(values: Sequence[Any],
            seed: Hash32) -> Iterable[Any]:
    """
    Returns the shuffled ``values`` with seed as entropy.
    Mainly for shuffling active validators.
    """
    values_count = len(values)

    # The size of 3 bytes in integer
    # sample_range = 2 ** (3 * 8) = 2 ** 24 = 16777216
    sample_range = 16777216

    if values_count > sample_range:
        raise ValueError(
            "values_count (%s) should less than or equal to sample_range (%s)." %
            (values_count, sample_range)
        )

    output = [x for x in values]
    source = seed
    index = 0
    while index < values_count:
        # Re-hash the source
        source = blake(source)
        for position in range(0, 30, 3):  # gets indices 3 bytes at a time
            # Select a 3-byte sampled int
            sample_from_source = int.from_bytes(source[position:position + 3], 'big')
            # `remaining` is the size of remaining indices of this round
            remaining = values_count - index
            if remaining == 0:
                break

            # Set a random maximum bound of sample_from_source
            rand_max = sample_range - sample_range % remaining

            # Select `replacement_position` with the given `sample_from_source` and `remaining`
            if sample_from_source < rand_max:
                # Use random number to get `replacement_position`, where it's not `index`
                replacement_position = (sample_from_source % remaining) + index
                # Swap the index-th and replacement_position-th elements
                (output[index], output[replacement_position]) = (
                    output[replacement_position],
                    output[index]
                )
                index += 1
            else:
                pass

    return output


@to_tuple
def split(seq: Sequence[TItem], pieces: int) -> Iterable[Any]:
    """
    Returns the split ``seq`` in ``pieces`` pieces.
    """
    list_length = len(seq)
    return [
        seq[(list_length * i // pieces): (list_length * (i + 1) // pieces)]
        for i in range(pieces)
    ]
