from typing import (
    Type,
)

from eth.rlp.blocks import BaseBlock
from eth.vm.forks.constantinople import (
    ConstantinopleVM,
)
from eth.vm.state import BaseState

from .blocks import IstanbulBlock
from .headers import (
    compute_istanbul_difficulty,
    configure_istanbul_header,
    create_istanbul_header_from_parent,
)
from .state import IstanbulState


class IstanbulVM(ConstantinopleVM):
    # fork name
    fork = "istanbul"

    # classes
    block_class: Type[BaseBlock] = IstanbulBlock
    _state_class: Type[BaseState] = IstanbulState

    # Methods
    create_header_from_parent = staticmethod(create_istanbul_header_from_parent)  # type: ignore  # noqa: E501
    compute_difficulty = staticmethod(compute_istanbul_difficulty)  # type: ignore
    configure_header = configure_istanbul_header
