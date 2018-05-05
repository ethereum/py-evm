from abc import (
    ABCMeta,
    abstractmethod
)
from typing import Union


class Unset:
    pass

unset = Unset()


class BaseDB(metaclass=ABCMeta):

    @abstractmethod
    def __init__(self) -> None:
        raise NotImplementedError(
            "The `init` method must be implemented by subclasses of BaseDB"
        )

    def get(self, key: bytes, default: Union[bytes, Unset] = unset) -> bytes:
        """
        Return the value for the given key.

        If the key doesn't exist, and a default is provided, return the default value.
        If the key doesn't exist, and a default is not provided, raise a KeyError

        :return: the value with the associated key
        :raise: KeyError if key is missing
        """
        try:
            return self[key]
        except KeyError as exc:
            if default is unset:
                raise exc
            else:
                return default


    @abstractmethod
    def set(self, key: bytes, value: bytes) -> None:
        raise NotImplementedError(
            "The `set` method must be implemented by subclasses of BaseDB"
        )

    @abstractmethod
    def exists(self, key: bytes) -> bool:
        """Return True if the key exists or False if it doesn't."""
        raise NotImplementedError(
            "The `exists` method must be implemented by subclasses of BaseDB"
        )

    @abstractmethod
    def delete(self, key: bytes) -> None:
        raise NotImplementedError(
            "The `delete` method must be implemented by subclasses of BaseDB"
        )

    #
    # Dictionary API
    #
    @abstractmethod
    def __getitem__(self, key: bytes) -> bytes:
        raise NotImplementedError(
            "The `__getitem__` method must be implemented by subclasses of BaseDB"
        )

    def __setitem__(self, key: bytes, value: bytes) -> None:
        return self.set(key, value)

    def __delitem__(self, key: bytes) -> None:
        return self.delete(key)

    def __contains__(self, key: bytes) -> bool:
        return self.exists(key)
