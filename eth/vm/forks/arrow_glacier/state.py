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
    ArrowGlacierMessageComputation,
)


class ArrowGlacierTransactionExecutor(LondonTransactionExecutor):
    pass


class ArrowGlacierState(LondonState):
    message_computation_class = ArrowGlacierMessageComputation
    transaction_executor_class: Type[TransactionExecutorAPI] = ArrowGlacierTransactionExecutor
