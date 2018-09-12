from asyncio import (  # noqa: F401
    Queue,
)
from typing import (
    Tuple,
    TypeVar,
)

from eth_utils import (
    ValidationError,
)

TQueueItem = TypeVar('TQueueItem')


async def queue_get_batch(
        queue: 'Queue[TQueueItem]',
        max_results: int = None) -> Tuple[TQueueItem, ...]:
    """
    Wait until at least one result is available, and return it and any
    other results that are immediately available, up to max_results.
    """
    if max_results is not None and max_results < 1:
        raise ValidationError("Must request at least one item from a queue, not {max_results!r}")

    # if the queue is empty, wait until at least one item is available
    if queue.empty():
        first_item = await queue.get()
    else:
        first_item = queue.get_nowait()

    # In order to return from queue_get_batch() as soon as possible, never await again.
    # Instead, take only the items that are already available.
    if max_results is None:
        remaining_count = None
    else:
        remaining_count = max_results - 1
    remaining_items = queue_get_nowait(queue, remaining_count)

    # Combine the first and remaining items
    return (first_item, ) + remaining_items


def queue_get_nowait(queue: 'Queue[TQueueItem]', max_results: int = None) -> Tuple[TQueueItem, ...]:
    # How many results do we want?
    available = queue.qsize()
    if max_results is None:
        num_items = available
    else:
        num_items = min((available, max_results))

    return tuple(queue.get_nowait() for _ in range(num_items))
