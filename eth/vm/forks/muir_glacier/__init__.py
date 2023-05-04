from typing import (
    Type,
)

from eth.rlp.blocks import BaseBlock
from eth.vm.forks.istanbul import (
    IstanbulVM,
)
from eth.vm.state import BaseState

from .blocks import MuirGlacierBlock
from .headers import (
    compute_muir_glacier_difficulty,
    configure_muir_glacier_header,
    create_muir_glacier_header_from_parent,
)
from .state import MuirGlacierState


class MuirGlacierVM(IstanbulVM):
    # fork name
    fork = "muir-glacier"

    # classes
    block_class: Type[BaseBlock] = MuirGlacierBlock
    _state_class: Type[BaseState] = MuirGlacierState

    # Methods
    create_header_from_parent = staticmethod(create_muir_glacier_header_from_parent)  # type: ignore  # noqa: E501
    compute_difficulty = staticmethod(compute_muir_glacier_difficulty)  # type: ignore
    configure_header = configure_muir_glacier_header
