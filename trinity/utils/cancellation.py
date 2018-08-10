import functools
from typing import (
    Any,
    Awaitable,
    Callable,
    TypeVar,
    Optional,
)

from cancel_token import OperationCancelled


TReturn = TypeVar('TReturn')


def async_handle_cancellation(awaitable_fn: Callable[..., Awaitable[TReturn]]
                              ) -> Callable[..., Awaitable[Optional[TReturn]]]:
    async def inner(*args: Any, **kwargs: Any) -> Optional[TReturn]:
        try:
            return await awaitable_fn(*args, **kwargs)
        except OperationCancelled:
            return None

    return functools.update_wrapper(inner, awaitable_fn)
