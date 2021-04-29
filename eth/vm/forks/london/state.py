from typing import Type

from eth.abc import (
    ComputationAPI,
    MessageAPI,
    SignedTransactionAPI,
    TransactionExecutorAPI,
)
from eth.vm.forks.berlin.state import (
    BerlinState,
    BerlinTransactionExecutor,
)

from .computation import LondonComputation


class LondonTransactionExecutor(BerlinTransactionExecutor):
    pass


class LondonState(BerlinState):
    computation_class = LondonComputation
    transaction_executor_class: Type[TransactionExecutorAPI] = LondonTransactionExecutor
