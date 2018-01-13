from evm.vm.forks.homestead.vm_state import HomesteadVMState

from .computation import TangerineWhistleComputation


class TangerineWhistleVMState(HomesteadVMState):
    computation_class = TangerineWhistleComputation
