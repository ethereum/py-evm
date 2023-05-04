from typing import (
    Type,
)

from eth.rlp.blocks import BaseBlock
from eth.vm.state import BaseState

from .blocks import GrayGlacierBlock
from .headers import (
    compute_gray_glacier_difficulty,
    configure_gray_glacier_header,
    create_gray_glacier_header_from_parent,
)
from .state import GrayGlacierState
from .. import ArrowGlacierVM


class GrayGlacierVM(ArrowGlacierVM):
    # fork name
    fork = "gray-glacier"

    # classes
    block_class: Type[BaseBlock] = GrayGlacierBlock
    _state_class: Type[BaseState] = GrayGlacierState

    # Methods
    create_header_from_parent = staticmethod(  # type: ignore
        create_gray_glacier_header_from_parent(compute_gray_glacier_difficulty)
    )
    compute_difficulty = staticmethod(compute_gray_glacier_difficulty)  # type: ignore
    configure_header = configure_gray_glacier_header
