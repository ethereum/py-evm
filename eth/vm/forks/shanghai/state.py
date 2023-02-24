from typing import Type

from eth.abc import (
    TransactionExecutorAPI,
    WithdrawalAPI,
)
from .computation import ShanghaiComputation
from ..paris import ParisState
from ..paris.state import ParisTransactionExecutor


class ShanghaiTransactionExecutor(ParisTransactionExecutor):
    pass


class ShanghaiState(ParisState):
    computation_class = ShanghaiComputation
    transaction_executor_class: Type[TransactionExecutorAPI] = ShanghaiTransactionExecutor   # noqa: E501

    def apply_withdrawal(self, withdrawal: WithdrawalAPI) -> None:
        # withdrawal amount is in gwei, convert to wei
        amount_in_wei = withdrawal.amount * 10 ** 9
        self.delta_balance(withdrawal.address, amount_in_wei)

        # delete account if it is empty
        if (
            self.get_balance(withdrawal.address) == 0
            and self.get_code(withdrawal.address) == b''
        ):
            self.delete_account(withdrawal.address)
