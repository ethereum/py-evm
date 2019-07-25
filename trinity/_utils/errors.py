from typing import (
    TypeVar
)
from typing_extensions import Protocol


class SupportsError(Protocol):
    error: Exception


TSupportsError = TypeVar('TSupportsError', bound=SupportsError)


def pass_or_raise(value: TSupportsError) -> TSupportsError:
    if value.error is not None:
        raise value.error

    return value
