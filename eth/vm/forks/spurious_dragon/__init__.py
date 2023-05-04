from typing import Type

from eth.abc import (
    BlockAPI,
    StateAPI,
)

from ..tangerine_whistle import TangerineWhistleVM

from .blocks import SpuriousDragonBlock
from .state import SpuriousDragonState


class SpuriousDragonVM(TangerineWhistleVM):
    # fork name
    fork: str = "spurious-dragon"

    # classes
    block_class: Type[BlockAPI] = SpuriousDragonBlock
    _state_class: Type[StateAPI] = SpuriousDragonState
