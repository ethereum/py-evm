from evm.vm.forks.homestead import HomesteadVM

from .state import TangerineWhistleState


class TangerineWhistleVM(HomesteadVM):
    # fork name
    fork = 'tangerine-whistle'

    # classes
    _state_class = TangerineWhistleState
