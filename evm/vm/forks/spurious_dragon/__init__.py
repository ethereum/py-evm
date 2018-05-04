from typing import Type  # noqa: F401
from evm.vm.state import BaseState  # noqa: F401

from ..tangerine_whistle import TangerineWhistleVM

from .state import SpuriousDragonState


class SpuriousDragonVM(TangerineWhistleVM):
    # fork name
    fork = 'spurious-dragon'  # type: str

    # classes
    _state_class = SpuriousDragonState  # type: Type[BaseState]
