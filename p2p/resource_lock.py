import asyncio
from collections.abc import Hashable
from typing import AsyncIterator
import weakref

from async_generator import asynccontextmanager


class ResourceLock:
    """
    Manage a set of locks for some set of hashable resources.
    """
    _locks: 'weakref.WeakKeyDictionary[Hashable, asyncio.Lock]'

    def __init__(self) -> None:
        self._locks = weakref.WeakKeyDictionary()

    @asynccontextmanager
    async def lock(self, resource: Hashable) -> AsyncIterator[None]:
        if resource not in self._locks:
            self._locks[resource] = asyncio.Lock()
        lock = self._locks[resource]
        async with lock:
            yield

    def is_locked(self, resource: Hashable) -> bool:
        if resource not in self._locks:
            return False
        else:
            return self._locks[resource].locked()
