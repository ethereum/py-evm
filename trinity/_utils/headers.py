from typing import (
    Awaitable,
    Callable,
    cast,
    Iterable,
    Tuple,
    TypeVar,
)

from eth.constants import UINT_256_MAX
from eth.rlp.headers import BlockHeader

from trinity.exceptions import OversizeObject


MAXIMUM_OBJECT_MEMORY_BYTES = 10000000

T = TypeVar('T', bound=int)


def sequence_builder(start_number: T,
                     max_length: int,
                     skip: int,
                     reverse: bool) -> Tuple[T, ...]:
    # Limit the in-memory size of this sequence.
    # A tuple of 64-bit ints is about 8 bytes per value
    # Ignore the cutoffs at 0 and UINT_256_MAX, because this is just a gut check anyway,
    # we should never be approaching this value.
    if max_length > MAXIMUM_OBJECT_MEMORY_BYTES // 8:
        raise OversizeObject(f"Sequence is too big to fit in memory: {max_length}")

    if reverse:
        step = -1 * (skip + 1)
    else:
        step = skip + 1

    cutoff_number = start_number + step * max_length

    whole_range = range(start_number, cutoff_number, step)

    return cast(
        Tuple[T, ...],
        tuple(number for number in whole_range if 0 <= number <= UINT_256_MAX)
    )


async def skip_complete_headers(
        headers_iter: Iterable[BlockHeader],
        completion_check: Callable[[BlockHeader], Awaitable[bool]]) -> Tuple[BlockHeader, ...]:
    """
    Collect all completed headers into a tuple, and the remaining headers into a second tuple,
    using `completion_check(header)` to decide on completion.

    Note that `completion_check` is *not* run on the remaining headers after the first time
    that it returns ``False``.

    Services should call self.wait() when using this method.
    """
    headers = tuple(headers_iter)
    for index, header in enumerate(headers):
        if not await completion_check(header):
            # index of first header that is not complete
            first_incomplete_index = index
            break
    else:
        first_incomplete_index = len(headers)

    return tuple(headers[:first_incomplete_index]), tuple(headers[first_incomplete_index:])
