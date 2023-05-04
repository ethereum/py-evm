from eth.vm.forks.istanbul.computation import (
    ISTANBUL_PRECOMPILES,
    IstanbulComputation,
)

from .opcodes import (
    MUIR_GLACIER_OPCODES,
)

MUIR_GLACIER_PRECOMPILES = ISTANBUL_PRECOMPILES


class MuirGlacierComputation(IstanbulComputation):
    """
    A class for all execution *message* computations in the ``MuirGlacier`` fork.
    Inherits from
    :class:`~eth.vm.forks.constantinople.istanbul.IstanbulComputation`
    """

    # Override
    opcodes = MUIR_GLACIER_OPCODES
    _precompiles = MUIR_GLACIER_PRECOMPILES
