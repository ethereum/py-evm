from evm.vm.forks.frontier.vm_state import FrontierVMState

from .blocks import HomesteadBlock
from .computation import HomesteadComputation
from .validation import validate_homestead_transaction


class HomesteadVMState(FrontierVMState):
    block_class = HomesteadBlock
    computation_class = HomesteadComputation

    def validate_transaction(self, transaction):
        validate_homestead_transaction(self, transaction)
