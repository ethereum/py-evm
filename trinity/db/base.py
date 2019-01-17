from abc import abstractmethod
from contextlib import contextmanager
from typing import (
    Generator,
)
# Typeshed definitions for multiprocessing.managers is incomplete, so ignore them for now:
# https://github.com/python/typeshed/blob/85a788dbcaa5e9e9a62e55f15d44530cd28ba830/stdlib/3/multiprocessing/managers.pyi#L3
from multiprocessing.managers import (  # type: ignore
    BaseProxy,
)

from eth.db.backends.base import BaseDB
from eth.db.atomic import AtomicDBWriteBatch

from trinity._utils.mp import async_method


class BaseAsyncDB(BaseDB):
    """
    Abstract base class extends the ``BaseDB`` with async APIs.
    """

    @abstractmethod
    async def coro_set(self, key: bytes, value: bytes) -> None:
        pass

    @abstractmethod
    async def coro_exists(self, key: bytes) -> bool:
        pass


class AsyncDBPreProxy(BaseAsyncDB):
    """
    Proxy implementation of ``BaseAsyncDB`` that does not derive from
    ``BaseProxy`` for the purpose of improved testability.
    """

    _exposed_ = (
        '__contains__',
        '__delitem__',
        '__getitem__',
        '__setitem__',
        'atomic_batch',
        'coro_set',
        'coro_exists',
        'delete',
        'exists',
        'get',
        'set',
    )

    def __init__(self) -> None:
        pass

    coro_set = async_method('set')
    coro_exists = async_method('exists')

    def get(self, key: bytes) -> bytes:
        return self._callmethod('get', (key,))

    def __getitem__(self, key: bytes) -> bytes:
        return self._callmethod('__getitem__', (key,))

    def set(self, key: bytes, value: bytes) -> None:
        return self._callmethod('set', (key, value))

    def __setitem__(self, key: bytes, value: bytes) -> None:
        return self._callmethod('__setitem__', (key, value))

    def delete(self, key: bytes) -> None:
        return self._callmethod('delete', (key,))

    def __delitem__(self, key: bytes) -> None:
        return self._callmethod('__delitem__', (key,))

    def exists(self, key: bytes) -> bool:
        return self._callmethod('exists', (key,))

    def __contains__(self, key: bytes) -> bool:
        return self._callmethod('__contains__', (key,))

    @contextmanager
    def atomic_batch(self) -> Generator['AtomicDBWriteBatch', None, None]:
        with AtomicDBWriteBatch._commit_unless_raises(self) as readable_batch:
            yield readable_batch


class AsyncDBProxy(BaseProxy, AsyncDBPreProxy):
    """
    Turn ``AsyncDBProxy`` into an actual proxy by deriving from ``BaseProxy``
    """
    pass
