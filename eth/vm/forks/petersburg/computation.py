from eth.vm.forks.byzantium.computation import (
    BYZANTIUM_PRECOMPILES
)
from eth.vm.forks.byzantium.computation import (
    ByzantiumMessageComputation
)

from .opcodes import PETERSBURG_OPCODES

PETERSBURG_PRECOMPILES = BYZANTIUM_PRECOMPILES


class PetersburgMessageComputation(ByzantiumMessageComputation):
    """
    A class for all execution *message* computations in the ``Petersburg`` fork.
    Inherits from
    :class:`~eth.vm.forks.byzantium.computation.ByzantiumMessageComputation`
    """
    # Override
    opcodes = PETERSBURG_OPCODES
    _precompiles = PETERSBURG_PRECOMPILES
