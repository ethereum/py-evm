from typing import Type  # noqa: F401
from evm.rlp.blocks import BaseBlock  # noqa: F401
from evm.vm.state import BaseState  # noqa: F401

from ..tangerine_whistle import TangerineWhistleVM

from .blocks import SpuriousDragonBlock
from .state import SpuriousDragonState


class SpuriousDragonVM(TangerineWhistleVM):
    # fork name
    fork = 'spurious-dragon'  # type: str

    # classes
    block_class = SpuriousDragonBlock  # type: Type[BaseBlock]
    _state_class = SpuriousDragonState  # type: Type[BaseState]
