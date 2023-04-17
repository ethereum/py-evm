from typing import Type

from eth.abc import TransactionExecutorAPI
from .computation import GrayGlacierMessageComputation
from ..arrow_glacier import ArrowGlacierState
from ..arrow_glacier.state import ArrowGlacierTransactionExecutor


class GrayGlacierTransactionExecutor(ArrowGlacierTransactionExecutor):
    pass


class GrayGlacierState(ArrowGlacierState):
    message_computation_class = GrayGlacierMessageComputation
    transaction_executor_class: Type[TransactionExecutorAPI] = GrayGlacierTransactionExecutor
