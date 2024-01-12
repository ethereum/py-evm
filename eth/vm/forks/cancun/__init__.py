from typing import (
    Type,
)

from eth.rlp.blocks import BaseBlock
from eth.vm.forks.shanghai import ShanghaiVM
from eth.vm.state import BaseState

from .blocks import CancunBlock
from .headers import (
    configure_cancun_header,
    create_cancun_header_from_parent,
)
from .state import CancunState


class CancunVM(ShanghaiVM):
    # fork name
    fork = "cancun"

    # classes
    block_class: Type[BaseBlock] = CancunBlock
    _state_class: Type[BaseState] = CancunState

    # methods
    create_header_from_parent = staticmethod(  # type: ignore
        create_cancun_header_from_parent()
    )
    configure_header = configure_cancun_header
