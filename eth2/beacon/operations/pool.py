from typing import Callable, Dict, Generic, Iterable, Iterator, Tuple, TypeVar, Union

from typing_extensions import Protocol

from eth2.beacon.typing import HashTreeRoot


class Operation(Protocol):
    hash_tree_root: HashTreeRoot


T = TypeVar("T", bound="Operation")


class OperationPool(Generic[T]):
    _pool_storage: Dict[HashTreeRoot, T]

    def __init__(self) -> None:
        self._pool_storage = {}

    def __len__(self) -> int:
        return len(self._pool_storage)

    def __iter__(self) -> Iterator[Tuple[HashTreeRoot, T]]:
        return iter(self._pool_storage.items())

    def __contains__(self, operation_or_root: Union[T, HashTreeRoot]) -> bool:
        if isinstance(operation_or_root, bytes):
            root = operation_or_root
        else:
            root = operation_or_root.hash_tree_root

        return root in self._pool_storage

    def get(self, hash_tree_root: HashTreeRoot) -> T:
        return self._pool_storage[hash_tree_root]

    def get_all(self) -> Tuple[T, ...]:
        return tuple(self._pool_storage.values())

    def _batch_do(self, f: Callable[[T], None], operations: Iterable[T]) -> None:
        for operation in operations:
            f(operation)

    def add(self, operation: T) -> None:
        self._pool_storage[operation.hash_tree_root] = operation

    def batch_add(self, operations: Iterable[T]) -> None:
        self._batch_do(self.add, operations)

    def remove(self, operation: T) -> None:
        root = operation.hash_tree_root
        if root in self._pool_storage:
            del self._pool_storage[root]

    def batch_remove(self, operations: Iterable[T]) -> None:
        self._batch_do(self.remove, operations)
