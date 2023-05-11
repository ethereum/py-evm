import fnmatch
import functools
import os
from typing import (
    Any,
    Callable,
    Iterable,
)

from eth_utils import (
    to_tuple,
)


@to_tuple
def recursive_find_files(base_dir: str, pattern: str) -> Iterable[str]:
    for dirpath, _, filenames in os.walk(base_dir):
        for filename in filenames:
            if fnmatch.fnmatch(filename, pattern):
                yield os.path.join(dirpath, filename)


def require_pytest(fn: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(fn)
    def inner(*args: Any, **kwargs: Any) -> Callable[..., Any]:
        try:
            import pytest  # noqa: F401
        except ImportError:
            raise ImportError(
                "pytest is required to use the fixture_tests.  Please ensure "
                "it is installed."
            )
        else:
            return fn(*args, **kwargs)

    return inner
