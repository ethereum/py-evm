import fnmatch
import functools
import os

from eth_utils import to_tuple


@to_tuple
def recursive_find_files(base_dir, pattern):
    for dirpath, _, filenames in os.walk(base_dir):
        for filename in filenames:
            if fnmatch.fnmatch(filename, pattern):
                yield os.path.join(dirpath, filename)


def require_pytest(fn):
    @functools.wraps(fn)
    def inner(*args, **kwargs):
        try:
            import pytest  # noqa: F401
        except ImportError:
            raise ImportError(
                'pytest is required to use the fixture_tests.  Please ensure '
                'it is installed.'
            )
        else:
            return fn(*args, **kwargs)
    return inner
