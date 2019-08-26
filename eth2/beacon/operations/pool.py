from typing import Dict, Generic, Iterator, Tuple, TypeVar

from eth_typing import Hash32
from typing_extensions import Protocol

HashTreeRoot = Hash32


class Operation(Protocol):
    hash_tree_root: HashTreeRoot


T = TypeVar("T", bound="Operation")


class OperationPool(Generic[T]):
    _pool_storage: Dict[HashTreeRoot, T]

    def __init__(self) -> None:
        self._pool_storage = {}

    def get(self, hash_tree_root: HashTreeRoot) -> T:
        return self._pool_storage[hash_tree_root]

    def add(self, operation: T) -> None:
        self._pool_storage[operation.hash_tree_root] = operation

    def __iter__(self) -> Iterator[Tuple[HashTreeRoot, T]]:
        return iter(self._pool_storage.items())
