from eth.vm.forks.petersburg.state import (
    PetersburgState,
)

from .computation import (
    IstanbulMessageComputation,
)


class IstanbulState(PetersburgState):
    message_computation_class = IstanbulMessageComputation
