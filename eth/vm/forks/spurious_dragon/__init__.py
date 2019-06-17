from typing import Type  # noqa: F401
from eth.rlp.blocks import BaseBlock  # noqa: F401
from eth.vm.state import BaseState  # noqa: F401

from ..tangerine_whistle import TangerineWhistleVM

from .blocks import SpuriousDragonBlock
from .state import SpuriousDragonState


class SpuriousDragonVM(TangerineWhistleVM):
    # fork name
    fork: str = 'spurious-dragon'  # noqa: E701  # flake8 bug that's fixed in 3.6.0+

    # classes
    block_class: Type[BaseBlock] = SpuriousDragonBlock
    _state_class: Type[BaseState] = SpuriousDragonState
