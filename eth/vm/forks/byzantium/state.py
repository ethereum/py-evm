from eth.vm.forks.spurious_dragon.state import SpuriousDragonState

from .computation import ByzantiumMessageComputation


class ByzantiumState(SpuriousDragonState):
    message_computation_class = ByzantiumMessageComputation
