from typing import Type

from eth.abc import (
    MessageComputationAPI,
    SignedTransactionAPI,
)
from eth.vm.forks.frontier.state import (
    FrontierState,
    FrontierTransactionExecutor,
)

from .computation import HomesteadMessageComputation
from .validation import validate_homestead_transaction


class HomesteadState(FrontierState):
    message_computation_class: Type[MessageComputationAPI] = HomesteadMessageComputation

    def validate_transaction(self, transaction: SignedTransactionAPI) -> None:
        validate_homestead_transaction(self, transaction)


class HomesteadTransactionExecutor(FrontierTransactionExecutor):
    pass
