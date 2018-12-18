import contextlib
import cProfile
import functools
from typing import (
    Any,
    Callable,
    Iterator,
)


@contextlib.contextmanager
def profiler(filename: str) -> Iterator[None]:
    pr = cProfile.Profile()
    pr.enable()
    try:
        yield
    finally:
        pr.disable()
        pr.dump_stats(filename)


def setup_cprofiler(filename: str) -> Callable[..., Any]:
    def outer(fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        def inner(*args: Any, **kwargs: Any) -> None:
            should_profile = kwargs.pop('profile', False)
            if should_profile:
                with profiler(filename):
                    return fn(*args, **kwargs)
            else:
                return fn(*args, **kwargs)
        return inner
    return outer
