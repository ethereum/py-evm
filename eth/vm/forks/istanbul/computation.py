from eth.vm.forks.constantinople.computation import (
    CONSTANTINOPLE_PRECOMPILES
)
from eth.vm.forks.constantinople.computation import (
    ConstantinopleComputation
)

from .opcodes import ISTANBUL_OPCODES

ISTANBUL_PRECOMPILES = CONSTANTINOPLE_PRECOMPILES


class IstanbulComputation(ConstantinopleComputation):
    """
    A class for all execution computations in the ``Istanbul`` fork.
    Inherits from :class:`~eth.vm.forks.constantinople.computation.ConstantinopleComputation`
    """
    # Override
    opcodes = ISTANBUL_OPCODES
    _precompiles = ISTANBUL_PRECOMPILES
