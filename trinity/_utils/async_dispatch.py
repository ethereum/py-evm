import asyncio
import functools
from typing import (
    Any,
    Awaitable,
    Callable
)


def async_method(method_name: str) -> Callable[..., Any]:
    async def method(self: Any, *args: Any, **kwargs: Any) -> Awaitable[Any]:
        loop = asyncio.get_event_loop()

        func = getattr(self, method_name)
        pfunc = functools.partial(func, *args, **kwargs)

        return await loop.run_in_executor(None, pfunc)
    return method
