from evm.vm.forks.homestead import HomesteadVM

from .computation import TangerineWhistleComputation
from .vm_state import TangerineWhistleVMState

TangerineWhistleVM = HomesteadVM.configure(
    name='TangerineWhistleVM',
    _computation_class=TangerineWhistleComputation,
    _state_class=TangerineWhistleVMState,
)
