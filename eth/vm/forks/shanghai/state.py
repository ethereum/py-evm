from typing import (
    Type,
)

from eth.abc import (
    TransactionExecutorAPI,
    WithdrawalAPI,
)

from ..paris import (
    ParisState,
)
from ..paris.state import (
    ParisTransactionExecutor,
)
from .computation import (
    ShanghaiComputation,
)


class ShanghaiTransactionExecutor(ParisTransactionExecutor):
    pass


class ShanghaiState(ParisState):
    computation_class = ShanghaiComputation
    transaction_executor_class: Type[
        TransactionExecutorAPI
    ] = ShanghaiTransactionExecutor

    def apply_withdrawal(self, withdrawal: WithdrawalAPI) -> None:
        # withdrawal amount is in gwei, convert to wei
        amount_in_wei = withdrawal.amount * 10**9
        self.delta_balance(withdrawal.address, amount_in_wei)
