from typing import (
    Tuple,
)

from eth.constants import UINT_256_MAX

from trinity.constants import MAXIMUM_OBJECT_MEMORY_BYTES
from trinity.exceptions import OversizeObject


def sequence_builder(start_number: int,
                     max_length: int,
                     skip: int,
                     reverse: bool) -> Tuple[int, ...]:
    # Limit the in-memory size of this sequence.
    # A tuple of 64-bit ints is about 8 bytes per value
    # Ignore the cutoffs at 0 and UINT_256_MAX, because this is just a gut check anyway,
    # we should never be approaching this value.
    if max_length > MAXIMUM_OBJECT_MEMORY_BYTES // 8:
        raise OversizeObject("Sequence is too big to fit in memory: {}".format(max_length))

    if reverse:
        step = -1 * (skip + 1)
    else:
        step = skip + 1

    cutoff_number = start_number + step * max_length

    whole_range = range(start_number, cutoff_number, step)

    return tuple(number for number in whole_range if 0 <= number <= UINT_256_MAX)
