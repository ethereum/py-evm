from typing import (
    AsyncIterator,
    Awaitable,
    Callable,
    cast,
    Iterable,
    Tuple,
    TypeVar,
)

from eth.constants import UINT_256_MAX
from eth.rlp.headers import BlockHeader
from eth.tools.logging import ExtendedDebugLogger

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
        headers: Iterable[BlockHeader],
        logger: ExtendedDebugLogger,
        completion_check: Callable[[BlockHeader], Awaitable[bool]]) -> Tuple[BlockHeader, ...]:
    """
    Skip any headers where `completion_check(header)` returns False
    After finding the first header that returns True, return all remaining headers.
    This is useful when importing headers in sequence, after writing them to DB in sequence.

    Services should call self.wait() when using this method
    """
    skip_headers_coro = _skip_complete_headers_iterator(headers, logger, completion_check)
    return tuple(
        # The inner list comprehension is needed because async_generators
        # cannot be cast to a tuple.
        [header async for header in skip_headers_coro]
    )


async def _skip_complete_headers_iterator(
        headers: Iterable[BlockHeader],
        logger: ExtendedDebugLogger,
        completion_check: Callable[[BlockHeader], Awaitable[bool]]) -> AsyncIterator[BlockHeader]:
    """
    We only want headers that are missing, so we iterate over the list
    until we find the first missing header, after which we return all of
    the remaining headers.
    """
    iter_headers = iter(headers)
    # for logging:
    first_discarded = None
    last_discarded = None
    num_discarded = 0
    for header in iter_headers:
        is_present = await completion_check(header)
        if is_present:
            if first_discarded is None:
                first_discarded = header
            else:
                last_discarded = header
            num_discarded += 1
        else:
            yield header
            break

    logger.debug(
        "Discarding %d headers that we already have: %s...%s",
        num_discarded,
        first_discarded,
        last_discarded,
    )

    for header in iter_headers:
        yield header
