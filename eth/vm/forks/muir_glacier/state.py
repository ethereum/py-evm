from eth.vm.forks.istanbul.state import (
    IstanbulState
)

from .computation import MuirGlacierMessageComputation


class MuirGlacierState(IstanbulState):
    message_computation_class = MuirGlacierMessageComputation
