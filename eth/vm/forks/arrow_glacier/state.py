from typing import Type

from eth.abc import TransactionExecutorAPI
from .computation import ArrowGlacierMessageComputation
from ..london import LondonState
from ..london.state import LondonTransactionExecutor


class ArrowGlacierTransactionExecutor(LondonTransactionExecutor):
    pass


class ArrowGlacierState(LondonState):
    message_computation_class = ArrowGlacierMessageComputation
    transaction_executor_class: Type[TransactionExecutorAPI] = ArrowGlacierTransactionExecutor
