from eth.vm.forks.gray_glacier.computation import (
    GrayGlacierMessageComputation,
)

from .opcodes import (
    PARIS_OPCODES,
)


class ParisMessageComputation(GrayGlacierMessageComputation):
    """
    A class for all execution *message* computations in the ``Paris`` hard fork
    Inherits from :class:`~eth.vm.forks.gray_glacier.GrayGlacierMessageComputation`
    """
    opcodes = PARIS_OPCODES
