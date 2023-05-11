from typing import (
    Type,
)

from eth.rlp.blocks import BaseBlock
from eth.vm.state import BaseState

from .blocks import ArrowGlacierBlock
from .headers import (
    compute_arrow_glacier_difficulty,
    configure_arrow_glacier_header,
    create_arrow_glacier_header_from_parent,
)
from .state import ArrowGlacierState
from .. import LondonVM


class ArrowGlacierVM(LondonVM):
    # fork name
    fork = "arrow-glacier"

    # classes
    block_class: Type[BaseBlock] = ArrowGlacierBlock
    _state_class: Type[BaseState] = ArrowGlacierState

    # Methods
    create_header_from_parent = staticmethod(  # type: ignore
        create_arrow_glacier_header_from_parent(compute_arrow_glacier_difficulty)
    )
    compute_difficulty = staticmethod(compute_arrow_glacier_difficulty)  # type: ignore
    configure_header = configure_arrow_glacier_header
