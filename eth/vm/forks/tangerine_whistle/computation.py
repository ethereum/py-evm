from ..homestead.computation import HomesteadMessageComputation

from .opcodes import TANGERINE_WHISTLE_OPCODES


class TangerineWhistleMessageComputation(HomesteadMessageComputation):
    """
    A class for all execution *message* computations in the ``TangerineWhistle`` fork.
    Inherits from
    :class:`~eth.vm.forks.homestead.computation.HomesteadMessageComputation`
    """
    # Override
    opcodes = TANGERINE_WHISTLE_OPCODES
