from ..homestead import HomesteadVM

from .state import SpuriousDragonState

SpuriousDragonVM = HomesteadVM.configure(
    # class name
    __name__='SpuriousDragonVM',
    # fork name
    fork='spurious-dragon',
    # classes
    _state_class=SpuriousDragonState,
)
