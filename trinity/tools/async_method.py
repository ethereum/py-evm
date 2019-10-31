import asyncio
from typing import Callable


async def wait_until_true(
    predicate: Callable[[], bool], timeout: float = 1.0
) -> bool:
    async def _check() -> bool:
        while True:
            if predicate():
                return True
            else:
                await asyncio.sleep(0)

    return await asyncio.wait_for(_check(), timeout=timeout)
