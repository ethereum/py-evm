from typing import (  # noqa: F401
    Type,
)

from eth.rlp.blocks import BaseBlock  # noqa: F401
from eth.vm.forks.byzantium import ByzantiumVM
from eth.vm.state import BaseState  # noqa: F401

from .blocks import ConstantinopleBlock
from .state import ConstantinopleState


class ConstantinopleVM(ByzantiumVM):
    # fork name
    fork = 'constantinople'

    # classes
    block_class = ConstantinopleBlock  # type: Type[BaseBlock]
    _state_class = ConstantinopleState  # type: Type[BaseState]
