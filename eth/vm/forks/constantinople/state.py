from eth.vm.forks.byzantium.state import (
    ByzantiumState,
)

from .computation import (
    ConstantinopleMessageComputation,
)


class ConstantinopleState(ByzantiumState):
    message_computation_class = ConstantinopleMessageComputation
