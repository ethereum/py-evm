from abc import (
    ABCMeta,
    abstractmethod
)


class BaseDB(metaclass=ABCMeta):

    @abstractmethod
    def __init__(self) -> None:
        raise NotImplementedError(
            "The `init` method must be implemented by subclasses of BaseDB"
        )

    @abstractmethod
    def get(self, key: bytes) -> bytes:
        """Return the value for the given key.

        Raises KeyError if key doesn't exist.
        """
        raise NotImplementedError(
            "The `get` method must be implemented by subclasses of BaseDB"
        )

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
    def __getitem__(self, key: bytes) -> bytes:
        return self.get(key)

    def __setitem__(self, key: bytes, value: bytes) -> None:
        return self.set(key, value)

    def __delitem__(self, key: bytes) -> None:
        return self.delete(key)

    def __contains__(self, key: bytes) -> bool:
        return self.exists(key)
