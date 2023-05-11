from typing import (
    Type,
)

from eth.abc import (
    TransactionExecutorAPI,
)

from ..arrow_glacier import (
    ArrowGlacierState,
)
from ..arrow_glacier.state import (
    ArrowGlacierTransactionExecutor,
)
from .computation import (
    GrayGlacierComputation,
)


class GrayGlacierTransactionExecutor(ArrowGlacierTransactionExecutor):
    pass


class GrayGlacierState(ArrowGlacierState):
    computation_class = GrayGlacierComputation
    transaction_executor_class: Type[
        TransactionExecutorAPI
    ] = GrayGlacierTransactionExecutor
