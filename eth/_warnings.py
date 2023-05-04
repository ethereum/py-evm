from contextlib import (
    contextmanager,
)
from typing import (
    Iterator,
)
import warnings


# TODO: drop once https://github.com/cython/cython/issues/1720 is resolved
@contextmanager
def catch_and_ignore_import_warning() -> Iterator[None]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=ImportWarning)
        yield
