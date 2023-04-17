from eth.vm.forks.homestead.state import HomesteadState

from .computation import TangerineWhistleComputation


class TangerineWhistleState(HomesteadState):
    message_computation_class = TangerineWhistleComputation
