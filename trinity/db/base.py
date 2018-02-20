from multiprocessing.managers import (
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
