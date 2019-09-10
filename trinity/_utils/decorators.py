from typing import (
    Any,
    Awaitable,
    Callable,
    Type,
    TypeVar,
)


TAsyncFn = TypeVar("TAsyncFn", bound=Callable[..., Awaitable[None]])


def async_suppress_exceptions(*exception_types: Type[BaseException]) -> TAsyncFn:
    def _suppress_decorator(func: TAsyncFn) -> TAsyncFn:
        async def _suppressed_func(*args: Any, **kwargs: Any) -> None:
            try:
                await func(*args, **kwargs)
            except exception_types:
                # these exceptions are expected, and require no handling
                pass

        return _suppressed_func  # type: ignore

    return _suppress_decorator  # type: ignore
