from ..homestead import HomesteadVM

from .state import SpuriousDragonState

SpuriousDragonVM = HomesteadVM.configure(
    __name__='SpuriousDragonVM',
    # classes
    _state_class=SpuriousDragonState,
)
