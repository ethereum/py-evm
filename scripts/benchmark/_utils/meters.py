import time
from typing import (
    Any,
    Callable,
    NamedTuple,
)


# FIXME: Couldn't get generics to work here. Sticking with `Any` for now
# See: https://stackoverflow.com/questions/50530959/generic-namedtuple-in-python-3-6
class TimedResult(NamedTuple):
    duration: float
    wrapped_value: Any


def time_call(fn: Callable[..., Any] = None) -> TimedResult:
    start = time.perf_counter()
    return_value = fn()
    duration = time.perf_counter() - start
    return TimedResult(duration=duration, wrapped_value=return_value)
