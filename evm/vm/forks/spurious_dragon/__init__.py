from ..homestead import HomesteadVM

from .blocks import SpuriousDragonBlock
from .vm_state import SpuriousDragonVMState

SpuriousDragonVM = HomesteadVM.configure(
    name='SpuriousDragonVM',
    # classes
    _block_class=SpuriousDragonBlock,
    _state_class=SpuriousDragonVMState,
)
