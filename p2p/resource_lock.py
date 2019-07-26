import asyncio
from collections.abc import Hashable
import weakref


class ResourceLock:
    """
    Manage a set of locks for some set of hashable resources.
    """
    _locks: 'weakref.WeakKeyDictionary[Hashable, asyncio.Lock]'

    def __init__(self) -> None:
        self._locks = weakref.WeakKeyDictionary()

    def lock(self, resource: Hashable) -> asyncio.Lock:
        if resource not in self._locks:
            self._locks[resource] = asyncio.Lock()
        lock = self._locks[resource]
        return lock

    def is_locked(self, resource: Hashable) -> bool:
        if resource not in self._locks:
            return False
        else:
            return self._locks[resource].locked()
