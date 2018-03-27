from evm.vm.forks.homestead import HomesteadVM

from .state import TangerineWhistleState

TangerineWhistleVM = HomesteadVM.configure(
    __name__='TangerineWhistleVM',
    _state_class=TangerineWhistleState,
)
