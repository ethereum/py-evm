import functools
import warnings
from typing import (
    Any,
    Callable,
    TypeVar,
    cast,
)


TFunc = TypeVar("TFunc", bound=Callable[..., Any])


def deprecate_method(func: TFunc, message: str = None) -> TFunc:
    @functools.wraps(func)
    def deprecated_func(*args: Any, **kwargs: Any) -> Any:
        warnings.warn(
            category=DeprecationWarning,
            message=(
                message
                or f"{func.__name__} is deprecated. "
                "A breaking change is expected in a future release."
            ),
        )
        func(*args, **kwargs)

    return cast(TFunc, deprecated_func)
