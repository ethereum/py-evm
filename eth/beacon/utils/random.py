
from typing import (
    Iterable,
    Any,
    Sequence,
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


def shuffle(values: Sequence[Any],
            seed: Hash32) -> Iterable[Any]:
    """
    TODO: docstring
    """
    values_count = len(values)
    max_list_count = 16777216
    if values_count > max_list_count:
        raise ValueError(
            "values_count (%s) should less than or equal to max_list_count(%s)." %
            (values_count, max_list_count)
        )

    output = [x for x in values]
    source = seed
    i = 0
    while i < values_count:
        source = blake(source)
        for pos in range(0, 30, 3):
            m = int.from_bytes(source[pos:pos + 3], 'big')
            remaining = values_count - i
            if remaining == 0:
                break
            rand_max = max_list_count - max_list_count % remaining
            if m < rand_max:
                replacement_pos = (m % remaining) + i
                output[i], output[replacement_pos] = output[replacement_pos], output[i]
                i += 1
    return output


@to_tuple
def split(lst: Sequence[Any], number: int) -> Iterable[Any]:
    list_length = len(lst)
    return [
        lst[(list_length * i // number): (list_length * (i + 1) // number)]
        for i in range(number)
    ]
