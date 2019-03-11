from typing import (
    cast,
    Iterable,
    AsyncIterator,
    Tuple,
    TypeVar,
)

from eth.constants import UINT_256_MAX
from eth.rlp.headers import BlockHeader
from p2p.service import BaseService

from trinity.db.eth1.header import BaseAsyncHeaderDB
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


async def skip_headers_in_db(
        headers: Iterable[BlockHeader],
        db: BaseAsyncHeaderDB,
        service: BaseService) -> Tuple[BlockHeader, ...]:
    skip_headers_coro = _skip_db_headers_iterator(headers, db, service)
    return tuple(
        # The inner list comprehension is needed because async_generators
        # cannot be cast to a tuple.
        [header async for header in service.wait_iter(skip_headers_coro)]
    )


async def _skip_db_headers_iterator(
        headers: Iterable[BlockHeader],
        db: BaseAsyncHeaderDB,
        service: BaseService) -> AsyncIterator[BlockHeader]:
    """
    We only want headers that are missing, so we iterate over the list
    until we find the first missing header, after which we return all of
    the remaining headers.
    """
    iter_headers = iter(headers)
    for header in iter_headers:
        is_present = await service.wait(db.coro_header_exists(header.hash))
        if is_present:
            service.logger.debug("Discarding header that we already have: %s", header)
        else:
            yield header
            break

    for header in iter_headers:
        yield header
