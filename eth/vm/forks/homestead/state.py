from eth.rlp.transactions import BaseTransaction

from eth.vm.forks.frontier.state import (
    FrontierState,
    FrontierTransactionExecutor,
)

from .computation import HomesteadComputation
from .validation import validate_homestead_transaction


class HomesteadState(FrontierState):
    computation_class = HomesteadComputation

    def validate_transaction(self, transaction: BaseTransaction) -> None:
        validate_homestead_transaction(self.account_db, transaction)


class HomesteadTransactionExecutor(FrontierTransactionExecutor):
    pass
