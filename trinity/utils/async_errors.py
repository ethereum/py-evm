from typing import (
    Awaitable,
    Optional,
    Tuple,
    TypeVar,
)


TReturn = TypeVar("TReturn")


async def await_and_wrap_errors(
        awaitable: Awaitable[TReturn]) -> Tuple[Optional[TReturn], Optional[Exception]]:
    try:
        val = await awaitable
    except Exception as e:
        return None, e
    else:
        return val, None
