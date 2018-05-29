# Typeshed definitions for multiprocessing.managers is incomplete, so ignore them for now:
# https://github.com/python/typeshed/blob/85a788dbcaa5e9e9a62e55f15d44530cd28ba830/stdlib/3/multiprocessing/managers.pyi#L3
from multiprocessing.managers import (  # type: ignore
    BaseProxy,
)


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
    )

    def get(self, key):
        return self._callmethod('get', (key,))

    def __getitem__(self, key):
        return self._callmethod('__getitem__', (key,))

    def set(self, key, value):
        return self._callmethod('set', (key, value))

    def __setitem__(self, key, value):
        return self._callmethod('__setitem__', (key, value))

    def delete(self, key):
        return self._callmethod('delete', (key,))

    def __delitem__(self, key):
        return self._callmethod('__delitem__', (key,))

    def exists(self, key):
        return self._callmethod('exists', (key,))

    def __contains__(self, key):
        return self._callmethod('__contains__', (key,))
