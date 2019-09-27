import asyncio
import operator
from typing import (
    Any,
    Awaitable,
    Callable,
    Iterable,
    Tuple,
    Union,
)

import trio


AsyncFnsAndArgsType = Union[
    Callable[..., Awaitable[Any]],
    Tuple[Any, ...],
]


async def gather(*async_fns_and_args: AsyncFnsAndArgsType) -> Tuple[Any, ...]:
    """Run a collection of async functions in parallel and collect their results.

    The results will be in the same order as the corresponding async functions.
    """
    indices_and_results = []

    async def get_result(index: int) -> None:
        async_fn_and_args = async_fns_and_args[index]
        if isinstance(async_fn_and_args, Iterable):
            async_fn, *args = async_fn_and_args
        elif asyncio.iscoroutinefunction(async_fn_and_args):
            async_fn = async_fn_and_args
            args = []
        else:
            raise TypeError(
                "Each argument must be either an async function or a tuple consisting of an "
                "async function followed by its arguments"
            )

        result = await async_fn(*args)
        indices_and_results.append((index, result))

    async with trio.open_nursery() as nursery:
        for index in range(len(async_fns_and_args)):
            nursery.start_soon(get_result, index)

    indices_and_results_sorted = sorted(indices_and_results, key=operator.itemgetter(0))
    return tuple(result for _, result in indices_and_results_sorted)
