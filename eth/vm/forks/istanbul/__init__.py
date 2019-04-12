from typing import (  # noqa: F401
    Type,
)

from eth.rlp.blocks import BaseBlock  # noqa: F401
from eth.vm.forks.constantinople import (
    ConstantinopleVM,
)
from eth.vm.state import BaseState  # noqa: F401

from .blocks import IstanbulBlock
from .headers import (
    compute_istanbul_difficulty,
    configure_istanbul_header,
    create_istanbul_header_from_parent,
)
from .state import IstanbulState


class IstanbulVM(ConstantinopleVM):
    # fork name
    fork = 'istanbul'

    # classes
    block_class = IstanbulBlock  # type: Type[BaseBlock]
    _state_class = IstanbulState  # type: Type[BaseState]

    # Methods
    create_header_from_parent = staticmethod(create_istanbul_header_from_parent)  # type: ignore  # noqa: E501
    compute_difficulty = staticmethod(compute_istanbul_difficulty)    # type: ignore
    configure_header = configure_istanbul_header
