import asyncio
import functools
from typing import (
    Any,
    Coroutine,
    Callable,
    TypeVar,
)


TReturn = TypeVar('TReturn')


def async_thread_method(method: Callable[..., TReturn],
                        ) -> Callable[..., Coroutine[Any, Any, TReturn]]:
    @functools.wraps(method)
    async def wrapper(self: Any, *args: Any, **kwargs: Any) -> TReturn:
        loop = asyncio.get_event_loop()

        return await loop.run_in_executor(
            None,
            functools.partial(method, **kwargs),
            self,
            *args
        )
    return wrapper
