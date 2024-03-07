from typing import (
    Any,
    Tuple,
    Type,
)

from eth_typing import (
    Address,
    Hash32,
)

from eth.abc import (
    ComputationAPI,
    TransactionExecutorAPI,
    TransientStorageAPI,
)
from eth.typing import (
    JournalDBCheckpoint,
)
from eth.vm.forks.shanghai import (
    ShanghaiState,
)
from eth.vm.transient_storage import (
    TransientStorage,
)

from ..shanghai.state import (
    ShanghaiTransactionExecutor,
)
from .computation import (
    CancunComputation,
)


class CancunTransactionExecutor(ShanghaiTransactionExecutor):
    def build_computation(self, *args: Any, **kwargs: Any) -> ComputationAPI:
        self.vm_state.reset_transient_storage()
        return super().build_computation(*args, **kwargs)


class CancunState(ShanghaiState):
    computation_class = CancunComputation
    transaction_executor_class: Type[TransactionExecutorAPI] = CancunTransactionExecutor

    _transient_storage_class: Type[TransientStorageAPI] = TransientStorage
    _transient_storage: TransientStorageAPI = None

    @property
    def transient_storage(self) -> TransientStorageAPI:
        if self._transient_storage is None:
            self.reset_transient_storage()

        return self._transient_storage

    def reset_transient_storage(self) -> None:
        self._transient_storage = self._transient_storage_class()

    def get_transient_storage(self, address: Address, slot: int) -> bytes:
        return self.transient_storage.get_transient_storage(address, slot)

    def set_transient_storage(self, address: Address, slot: int, value: bytes) -> None:
        return self.transient_storage.set_transient_storage(address, slot, value)

    def snapshot(self) -> Tuple[Hash32, JournalDBCheckpoint]:
        state_root, checkpoint = super().snapshot()
        self.transient_storage.record(checkpoint)
        return state_root, checkpoint

    def commit(self, snapshot: Tuple[Hash32, JournalDBCheckpoint]) -> None:
        super().commit(snapshot)
        _, checkpoint = snapshot
        self.transient_storage.commit(checkpoint)

    def revert(self, snapshot: Tuple[Hash32, JournalDBCheckpoint]) -> None:
        super().revert(snapshot)
        _, checkpoint = snapshot
        self.transient_storage.discard(checkpoint)
