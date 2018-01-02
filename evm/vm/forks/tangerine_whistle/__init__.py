from evm.vm.forks.homestead import HomesteadVM

from .vm_state import TangerineWhistleVMState

TangerineWhistleVM = HomesteadVM.configure(
    name='TangerineWhistleVM',
    _state_class=TangerineWhistleVMState,
)
