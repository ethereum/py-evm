import asyncio
import itertools
import operator
from typing import (
    Any,
    AsyncGenerator,
    Awaitable,
    Callable,
    Iterable,
    Optional,
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


async def every(interval: float,
                initial_delay: float = 0,
                ) -> AsyncGenerator[float, Optional[float]]:
    """Generator used to perform a task in regular intervals.

    The generator will attempt to yield at a sequence of target times, defined as
    `start_time + initial_delay + N * interval` seconds where `start_time` is trio's current time
    at instantiation of the generator and `N` starts at `0`. The target time is also the value that
    is yielded.

    If at a certain iteration the target time has already passed, the generator will yield
    immediately (with a checkpoint in between). The yield value is still the target time.

    The generator accepts an optional send value which will delay the next and all future
    iterations of the generator by that amount.
    """
    start_time = trio.current_time()
    undelayed_yield_times = (
        start_time + interval * iteration for iteration in itertools.count()
    )
    delay = initial_delay

    for undelayed_yield_time in undelayed_yield_times:
        yield_time = undelayed_yield_time + delay
        await trio.sleep_until(yield_time)

        additional_delay = yield yield_time
        if additional_delay is not None:
            delay += additional_delay
