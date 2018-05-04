from typing import Type  # noqa: F401
from evm.vm.state import BaseState  # noqa: F401

from evm.vm.forks.homestead import HomesteadVM

from .state import TangerineWhistleState


class TangerineWhistleVM(HomesteadVM):
    # fork name
    fork = 'tangerine-whistle'  # type: str

    # classes
    _state_class = TangerineWhistleState  # type: Type[BaseState]
