from evm.vm.forks.frontier.state import FrontierState

from .blocks import HomesteadBlock
from .computation import HomesteadComputation
from .validation import validate_homestead_transaction


class HomesteadState(FrontierState):
    block_class = HomesteadBlock
    computation_class = HomesteadComputation

    def validate_transaction(self, transaction):
        validate_homestead_transaction(self, transaction)
