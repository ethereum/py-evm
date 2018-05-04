from ..tangerine_whistle import TangerineWhistleVM

from .state import SpuriousDragonState


class SpuriousDragonVM(TangerineWhistleVM):
    # fork name
    fork = 'spurious-dragon'

    # classes
    _state_class = SpuriousDragonState
