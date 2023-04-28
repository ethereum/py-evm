from typing import Type

from eth.abc import (
    StateAPI,
    TransactionExecutorAPI,
)
from eth_typing import Hash32
from .computation import ParisComputation
from ..gray_glacier import GrayGlacierState
from ..gray_glacier.state import GrayGlacierTransactionExecutor


class ParisTransactionExecutor(GrayGlacierTransactionExecutor):
    pass


class ParisState(GrayGlacierState):
    computation_class = ParisComputation
    transaction_executor_class: Type[TransactionExecutorAPI] = ParisTransactionExecutor

    @property
    def mix_hash(self: StateAPI) -> Hash32:
        return self.execution_context.mix_hash
