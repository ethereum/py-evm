import contextlib
import cProfile
import functools
from typing import Callable


@contextlib.contextmanager
def profiler(filename):
    pr = cProfile.Profile()
    pr.enable()
    try:
        yield
    finally:
        pr.disable()
        pr.dump_stats(filename)


def setup_cprofiler(filename):
    def outer(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def inner(*args, **kwargs):
            should_profile = kwargs.pop('profile', False)
            if should_profile:
                with profiler(filename):
                    return fn(*args, **kwargs)
            else:
                return fn(*args, **kwargs)
        return inner
    return outer
