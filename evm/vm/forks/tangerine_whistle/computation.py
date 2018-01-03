from ..homestead.computation import HomesteadComputation

from .opcodes import TANGERINE_WHISTLE_OPCODES


class TangerineWhistleComputation(HomesteadComputation):
    # Override
    opcodes = TANGERINE_WHISTLE_OPCODES
