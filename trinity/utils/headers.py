from typing import (
    Tuple,
)

from eth.constants import UINT_256_MAX


def sequence_builder(start_number: int,
                     max_length: int,
                     skip: int,
                     reverse: bool) -> Tuple[int, ...]:
    if reverse:
        step = -1 * (skip + 1)
    else:
        step = skip + 1

    cutoff_number = start_number + step * max_length

    whole_range = range(start_number, cutoff_number, step)

    return tuple(number for number in whole_range if 0 <= number <= UINT_256_MAX)
