from typing import Iterable, Tuple

from eth_utils.toolz import sliding_window


def _find_breakpoints(*values: int) -> Iterable[int]:
    yield 0
    for index, (left, right) in enumerate(sliding_window(2, values), 1):
        if left + 1 == right:
            continue
        else:
            yield index
    yield len(values)


def _extract_integer_ranges(*values: int) -> Iterable[Tuple[int, int]]:
    """
    Take a sequence of integers which is expected to be ordered and return the
    most concise definition of the sequence in terms of integer ranges.

    - fn(1, 2, 3) -> ((1, 3),)
    - fn(1, 2, 3, 7, 8, 9) -> ((1, 3), (7, 9))
    - fn(1, 7, 8, 9) -> ((1, 1), (7, 9))
    """
    for left, right in sliding_window(2, _find_breakpoints(*values)):
        chunk = values[left:right]
        yield chunk[0], chunk[-1]


def _humanize_range(bounds: Tuple[int, int]) -> str:
    left, right = bounds
    if left == right:
        return str(left)
    else:
        return f'{left}-{right}'


def humanize_integer_sequence(values_iter: Iterable[int]) -> str:
    """
    Return a human readable string that attempts to concisely define a sequence
    of integers.

    - fn((1, 2, 3)) -> '1-3'
    - fn((1, 2, 3, 7, 8, 9)) -> '1-3|7-9'
    - fn((1, 2, 3, 5, 7, 8, 9)) -> '1-3|5|7-9'
    - fn((1, 7, 8, 9)) -> '1|7-9'
    """
    values = tuple(values_iter)
    if not values:
        return "(empty)"
    else:
        return '|'.join(map(_humanize_range, _extract_integer_ranges(*values)))
