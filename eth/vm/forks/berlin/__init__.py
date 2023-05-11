from typing import (
    Type,
)

from eth.rlp.blocks import BaseBlock
from eth.vm.forks import (
    MuirGlacierVM,
)
from eth.vm.state import BaseState

from .blocks import BerlinBlock
from .headers import (
    compute_berlin_difficulty,
    configure_berlin_header,
    create_berlin_header_from_parent,
)
from .state import BerlinState


class BerlinVM(MuirGlacierVM):
    # fork name
    fork = "berlin"

    # classes
    block_class: Type[BaseBlock] = BerlinBlock
    _state_class: Type[BaseState] = BerlinState

    # Methods
    create_header_from_parent = staticmethod(create_berlin_header_from_parent)  # type: ignore  # noqa: E501
    compute_difficulty = staticmethod(compute_berlin_difficulty)  # type: ignore
    configure_header = configure_berlin_header
