from typing import (
    Any,
    Awaitable,
    Callable,
    Type,
    TypeVar,
)


TAsyncFn = TypeVar("TAsyncFn", bound=Callable[..., Awaitable[None]])


class classproperty(property):
    def __get__(self, obj: Any, objtype: Any = None) -> Any:
        return super().__get__(objtype)


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
