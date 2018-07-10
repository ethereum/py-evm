from typing import Type  # noqa: F401
from eth.vm.state import BaseState  # noqa: F401

from eth.vm.forks.homestead import HomesteadVM

from .state import TangerineWhistleState


class TangerineWhistleVM(HomesteadVM):
    # fork name
    fork = 'tangerine-whistle'  # type: str

    # classes
    _state_class = TangerineWhistleState  # type: Type[BaseState]

    # Don't bother with any DAO logic in Tangerine VM or later
    # This is how we skip DAO logic on Ropsten, for example
    support_dao_fork = False
