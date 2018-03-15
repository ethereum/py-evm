from abc import (
    ABCMeta,
    abstractmethod
)


class BaseDB(metaclass=ABCMeta):

    @abstractmethod
    def get(self, key):
        raise NotImplementedError(
            "The `get` method must be implemented by subclasses of BaseDB"
        )

    @abstractmethod
    def set(self, key, value):
        raise NotImplementedError(
            "The `set` method must be implemented by subclasses of BaseDB"
        )

    @abstractmethod
    def exists(self, key):
        raise NotImplementedError(
            "The `exists` method must be implemented by subclasses of BaseDB"
        )

    @abstractmethod
    def delete(self, key):
        raise NotImplementedError(
            "The `delete` method must be implemented by subclasses of BaseDB"
        )

    #
    # Dictionary API
    #
    def __getitem__(self, key):
        return self.get(key)

    def __setitem__(self, key, value):
        return self.set(key, value)

    def __delitem__(self, key):
        return self.delete(key)

    def __contains__(self, key):
        return self.exists(key)
