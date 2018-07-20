from typing import (
    Iterator,
)

from eth_utils import to_tuple

from eth.constants import UINT_256_MAX


@to_tuple
def sequence_builder(start_number: int,
                     max_length: int,
                     skip: int,
                     reverse: bool) -> Iterator[int]:
    if reverse:
        step = -1 * (skip + 1)
    else:
        step = skip + 1

    cutoff_number = start_number + step * max_length

    for number in range(start_number, cutoff_number, step):
        if number < 0 or number > UINT_256_MAX:
            return
        else:
            yield number
