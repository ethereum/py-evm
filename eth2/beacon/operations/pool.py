from typing import Dict, Generic, Iterator, Tuple, TypeVar
from typing_extensions import Protocol

from eth_typing import Hash32


Root = Hash32


class Operation(Protocol):
    root: Root


T = TypeVar('T', bound='Operation')


class OperationPool(Generic[T]):
    _pool_storage: Dict[Root, T]

    def __init__(self) -> None:
        self._pool_storage = {}

    def get(self, root: Root) -> T:
        return self._pool_storage[root]

    def add(self, operation: T) -> None:
        self._pool_storage[operation.root] = operation

    def __iter__(self) -> Iterator[Tuple[Root, T]]:
        return iter(self._pool_storage.items())
