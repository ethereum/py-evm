from typing import (
    Type,
)

from eth.abc import (
    TransactionExecutorAPI,
)

from ..shanghai import (
    ShanghaiState,
)
from ..shanghai.state import (
    ShanghaiTransactionExecutor,
)
from .computation import (
    CancunComputation,
)


class CancunTransactionExecutor(ShanghaiTransactionExecutor):
    pass


class CancunState(ShanghaiState):
    computation_class = CancunComputation
    transaction_executor_class: Type[TransactionExecutorAPI] = CancunTransactionExecutor
