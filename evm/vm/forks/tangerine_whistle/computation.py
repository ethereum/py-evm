from ..homestead.computation import HomesteadComputation

from .opcodes import TANGERINE_WHISTLE_OPCODES


class TangerineWhistleComputation(HomesteadComputation):
    def __init__(self, vm_state, message):
        super(TangerineWhistleComputation, self).__init__(
            vm_state,
            message,
        )
        # Override
        self.opcodes = TANGERINE_WHISTLE_OPCODES
