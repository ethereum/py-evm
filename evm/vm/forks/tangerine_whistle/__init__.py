from evm.vm.forks.homestead import HomesteadVM

from .vm_state import TangerineWhistleVMState

TangerineWhistleVM = HomesteadVM.configure(
    __name__='TangerineWhistleVM',
    _state_class=TangerineWhistleVMState,
)
