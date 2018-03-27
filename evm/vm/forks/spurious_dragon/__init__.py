from ..homestead import HomesteadVM

from .blocks import SpuriousDragonBlock
from .state import SpuriousDragonState

SpuriousDragonVM = HomesteadVM.configure(
    __name__='SpuriousDragonVM',
    # classes
    _block_class=SpuriousDragonBlock,
    _state_class=SpuriousDragonState,
)
