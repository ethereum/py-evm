from abc import (
    ABCMeta,
    abstractmethod
)
from collections.abc import (
    MutableMapping,
)


class BaseDB(MutableMapping, metaclass=ABCMeta):
    """
    This is an abstract key/value lookup with all :class:`bytes` values,
    with some convenience methods for databases. As much as possible,
    you can use a DB as if it were a :class:`dict`.

    Notable exceptions are that you cannot iterate through all values or get the length.
    (Unless a subclass explicitly enables it).

    All subclasses must implement these methods:
    __getitem__, __setitem__, __delitem__

    Subclasses may optionally implement an _exists method
    that is type-checked for key and value.
    """

    @abstractmethod
    def __init__(self) -> None:
        raise NotImplementedError(
            "The `init` method must be implemented by subclasses of BaseDB"
        )

    def set(self, key: bytes, value: bytes) -> None:
        self[key] = value

    def exists(self, key: bytes) -> bool:
        return self.__contains__(key)

    def __contains__(self, key):
        if hasattr(self, '_exists'):
            return self._exists(key)
        else:
            return super().__contains__(key)

    def delete(self, key: bytes) -> None:
        try:
            del self[key]
        except KeyError:
            return None

    def __iter__(self):
        raise NotImplementedError("By default, DB classes cannot by iterated.")

    def __len__(self):
        raise NotImplementedError("By default, DB classes cannot return the total number of keys.")
