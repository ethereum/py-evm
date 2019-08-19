import asyncio
import functools
from typing import (
    Any,
    Coroutine,
    Callable,
    TypeVar,
)

TReturn = TypeVar('TReturn')


def async_method(method: Callable[..., TReturn],
                 ) -> Callable[..., Coroutine[Any, Any, TReturn]]:
    @functools.wraps(method)
    async def wrapper(cls_or_self: Any, *args: Any, **kwargs: Any) -> TReturn:
        cls_method = getattr(cls_or_self, method.__name__)
        loop = asyncio.get_event_loop()

        return await loop.run_in_executor(
            None,
            functools.partial(cls_method, **kwargs),
            *args
        )
    return wrapper
