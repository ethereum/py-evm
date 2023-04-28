from typing import Type

from eth.abc import TransactionExecutorAPI
from .computation import ArrowGlacierComputation
from ..london import LondonState
from ..london.state import LondonTransactionExecutor


class ArrowGlacierTransactionExecutor(LondonTransactionExecutor):
    pass


class ArrowGlacierState(LondonState):
    computation_class = ArrowGlacierComputation
    transaction_executor_class: Type[TransactionExecutorAPI] = ArrowGlacierTransactionExecutor
