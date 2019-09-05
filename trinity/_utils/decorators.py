import functools
from typing import (
    Any,
    Awaitable,
    Callable,
    Type,
)


class classproperty(property):
    def __get__(self, obj: Any, objtype: Any = None) -> Any:
        return super().__get__(objtype)


def suppress_exceptions(*exception_types: Type[BaseException]) -> Callable[..., Any]:
    def _suppress_decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def _suppressed_func(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except exception_types:
                # these exceptions are expected, and require no handling
                pass

        return _suppressed_func

    return _suppress_decorator


def async_suppress_exceptions(*exception_types: Type[BaseException]) -> Callable[..., Any]:
    def _suppress_decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        async def _suppressed_func(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except exception_types:
                # these exceptions are expected, and require no handling
                pass

        return _suppressed_func

    return _suppress_decorator
