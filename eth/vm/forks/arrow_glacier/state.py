from typing import (
    Type,
)

from eth.abc import (
    TransactionExecutorAPI,
)

from ..london import (
    LondonState,
)
from ..london.state import (
    LondonTransactionExecutor,
)
from .computation import (
    ArrowGlacierComputation,
)


class ArrowGlacierTransactionExecutor(LondonTransactionExecutor):
    pass


class ArrowGlacierState(LondonState):
    computation_class = ArrowGlacierComputation
    transaction_executor_class: Type[
        TransactionExecutorAPI
    ] = ArrowGlacierTransactionExecutor
