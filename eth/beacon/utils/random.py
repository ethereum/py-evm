
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
from eth.beacon.constants import (
    SAMPLE_RANGE,
)


TItem = TypeVar('TItem')


def shuffle(values: Sequence[Any],
            seed: Hash32) -> Iterable[Any]:
    """
    Returns the shuffled ``values`` with seed as entropy.
    Mainly for shuffling active validators in-protocol.

    Spec: https://github.com/ethereum/eth2.0-specs/blob/0941d592de7546a428066c0473fd1000a7e3e3af/specs/beacon-chain.md#helper-functions  # noqa: E501
    """
    values_count = len(values)

    if values_count > SAMPLE_RANGE:
        raise ValueError(
            "values_count (%s) should less than or equal to SAMPLE_RANGE (%s)." %
            (values_count, SAMPLE_RANGE)
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
            rand_max = SAMPLE_RANGE - SAMPLE_RANGE % remaining

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
    Returns the split ``seq`` in ``pieces`` pieces in protocol.
    Spec: https://github.com/ethereum/eth2.0-specs/blob/0941d592de7546a428066c0473fd1000a7e3e3af/specs/beacon-chain.md#helper-functions  # noqa: E501
    """
    list_length = len(seq)
    return [
        seq[(list_length * i // pieces): (list_length * (i + 1) // pieces)]
        for i in range(pieces)
    ]
