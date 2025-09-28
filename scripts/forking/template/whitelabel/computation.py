from eth.vm.forks.petersburg.computation import (
    PETERSBURG_PRECOMPILES
)
from eth.vm.forks.petersburg.computation import (
    PetersburgComputation,
)

from .opcodes import ISTANBUL_OPCODES

ISTANBUL_PRECOMPILES = PETERSBURG_PRECOMPILES


class IstanbulComputation(PetersburgComputation):
    """
    A class for all execution computations in the ``Istanbul`` fork.
    Inherits from :class:`~eth.vm.forks.petersburg.PetersburgComputation`
    """
    # Override
    opcodes = ISTANBUL_OPCODES
    _precompiles = ISTANBUL_PRECOMPILES
