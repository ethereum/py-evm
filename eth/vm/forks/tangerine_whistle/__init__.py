from typing import Type
from eth.vm.state import BaseState

from eth.vm.forks.homestead import HomesteadVM

from .state import TangerineWhistleState


class TangerineWhistleVM(HomesteadVM):
    # fork name
    fork: str = 'tangerine-whistle'  # noqa

    # classes
    _state_class: Type[BaseState] = TangerineWhistleState

    # Don't bother with any DAO logic in Tangerine VM or later
    # This is how we skip DAO logic on Ropsten, for example
    support_dao_fork = False
