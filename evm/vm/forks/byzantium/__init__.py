from evm.vm.forks.spurious_dragon import SpuriousDragonVM

from .headers import (
    create_byzantium_header_from_parent,
    configure_byzantium_header,
    compute_byzantium_difficulty,
)
from .state import ByzantiumState


ByzantiumVM = SpuriousDragonVM.configure(
    # class name
    __name__='ByzantiumVM',
    # fork name
    fork='byzantium',
    # classes
    _state_class=ByzantiumState,
    # Methods
    create_header_from_parent=staticmethod(create_byzantium_header_from_parent),
    compute_difficulty=staticmethod(compute_byzantium_difficulty),
    configure_header=configure_byzantium_header,
)
