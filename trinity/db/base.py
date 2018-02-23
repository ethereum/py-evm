# Typeshed definitions for multiprocessing.managers is incomplete, so ignore them for now:
# https://github.com/python/typeshed/blob/85a788dbcaa5e9e9a62e55f15d44530cd28ba830/stdlib/3/multiprocessing/managers.pyi#L3
from multiprocessing.managers import (  # type: ignore
    BaseProxy,
)


class DBProxy(BaseProxy):
    _exposed_ = (
        'get',
        'set',
        'delete',
        'exists',
    )

    def __getitem__(self, key):
        return self._callmethod('get', (key,))

    def __setitem__(self, key, value):
        return self._callmethod('set', (key, value))

    def __delitem__(self, key):
        return self._callmethod('delete', (key,))

    def __contains__(self, key):
        return self._callmethod('exists', (key,))
