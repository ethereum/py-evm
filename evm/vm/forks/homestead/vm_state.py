from evm.vm.forks.frontier.vm_state import FrontierVMState

from .computation import HomesteadComputation
from .validation import validate_homestead_transaction


class HomesteadVMState(FrontierVMState):
    computation_class = HomesteadComputation

    def validate_transaction(self, transaction):
        validate_homestead_transaction(self, transaction)
