from ..homestead import HomesteadVM

from .blocks import SpuriousDragonBlock
from .computation import SpuriousDragonComputation
from .vm_state import SpuriousDragonVMState

SpuriousDragonVM = HomesteadVM.configure(
    name='SpuriousDragonVM',
    # classes
    _block_class=SpuriousDragonBlock,
    _computation_class=SpuriousDragonComputation,
    _state_class=SpuriousDragonVMState,
)
