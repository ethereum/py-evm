from evm.vm.forks.frontier.state import FrontierState

from .computation import HomesteadComputation
from .validation import validate_homestead_transaction


class HomesteadState(FrontierState):
    computation_class = HomesteadComputation

    def validate_transaction(self, transaction):
        validate_homestead_transaction(self.account_db, transaction)
