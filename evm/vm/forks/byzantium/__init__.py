from evm.vm.forks.spurious_dragon import SpuriousDragonVM

from .headers import (
    create_byzantium_header_from_parent,
    configure_byzantium_header,
    compute_byzantium_difficulty,
)
from .blocks import ByzantiumBlock
from .vm_state import ByzantiumVMState


ByzantiumVM = SpuriousDragonVM.configure(
    __name__='ByzantiumVM',
    # classes
    _block_class=ByzantiumBlock,
    _state_class=ByzantiumVMState,
    # Methods
    create_header_from_parent=staticmethod(create_byzantium_header_from_parent),
    compute_difficulty=staticmethod(compute_byzantium_difficulty),
    configure_header=configure_byzantium_header,
)
