# Typeshed definitions for multiprocessing.managers is incomplete, so ignore them for now:
# https://github.com/python/typeshed/blob/85a788dbcaa5e9e9a62e55f15d44530cd28ba830/stdlib/3/multiprocessing/managers.pyi#L3
from multiprocessing.managers import (  # type: ignore
    BaseProxy,
)

from eth.db.backends.base import BaseDB

from trinity.utils.mp import async_method


class DBProxy(BaseProxy):
    _exposed_ = (
        '__contains__',
        '__delitem__',
        '__getitem__',
        '__setitem__',
        'delete',
        'exists',
        'get',
        'set',
        'coro_set',
        'coro_exists',
    )
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


class AsyncBaseDB(BaseDB):

    async def coro_set(self, key: bytes, value: bytes) -> None:
        raise NotImplementedError()

    async def coro_exists(self, key: bytes) -> bool:
        raise NotImplementedError()
