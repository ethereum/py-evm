from evm.vm.forks.homestead import HomesteadVM

from .state import TangerineWhistleState

TangerineWhistleVM = HomesteadVM.configure(
    # class name
    __name__='TangerineWhistleVM',
    # fork name
    fork='tangerine-whistle',
    # classes
    _state_class=TangerineWhistleState,
)
