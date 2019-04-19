from eth.vm.forks.frontier.state import (
    FrontierState,
    FrontierTransactionExecutor,
)

from .computation import HomesteadComputation
from .validation import validate_homestead_transaction


class HomesteadState(FrontierState):
    computation_class = HomesteadComputation

    validate_transaction = validate_homestead_transaction


class HomesteadTransactionExecutor(FrontierTransactionExecutor):
    pass
