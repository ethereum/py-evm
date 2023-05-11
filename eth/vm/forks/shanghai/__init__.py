from typing import (
    Type,
)

from eth.rlp.blocks import BaseBlock
from eth.vm.forks.paris import ParisVM
from eth.vm.state import BaseState

from .blocks import ShanghaiBlock
from .headers import (
    configure_shanghai_header,
    create_shanghai_header_from_parent,
)
from .state import ShanghaiState


class ShanghaiVM(ParisVM):
    # fork name
    fork = "shanghai"

    # classes
    block_class: Type[BaseBlock] = ShanghaiBlock
    _state_class: Type[BaseState] = ShanghaiState

    # Methods
    create_header_from_parent = staticmethod(  # type: ignore
        create_shanghai_header_from_parent()
    )
    configure_header = configure_shanghai_header
