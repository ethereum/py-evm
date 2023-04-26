from eth.vm.forks.homestead.state import (
    HomesteadState,
)

from .computation import (
    TangerineWhistleMessageComputation,
)


class TangerineWhistleState(HomesteadState):
    message_computation_class = TangerineWhistleMessageComputation
