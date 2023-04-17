from eth.vm.forks.byzantium.state import (
    ByzantiumState
)

from .computation import PetersburgMessageComputation


class PetersburgState(ByzantiumState):
    message_computation_class = PetersburgMessageComputation
