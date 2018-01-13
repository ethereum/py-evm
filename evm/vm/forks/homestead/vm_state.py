from evm.vm.forks.frontier.vm_state import FrontierVMState

from .computation import HomesteadComputation


class HomesteadVMState(FrontierVMState):
    computation_class = HomesteadComputation
