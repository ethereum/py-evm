from typing import Type

from eth.abc import (
    TransactionExecutorAPI,
)
from .computation import ShanghaiComputation
from ..paris import ParisState
from ..paris.state import ParisTransactionExecutor


class ShanghaiTransactionExecutor(ParisTransactionExecutor):
    pass


class ShanghaiState(ParisState):
    computation_class = ShanghaiComputation
    transaction_executor_class: Type[TransactionExecutorAPI] = ShanghaiTransactionExecutor   # noqa: E501
