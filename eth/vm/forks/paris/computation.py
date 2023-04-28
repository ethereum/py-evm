from .opcodes import PARIS_OPCODES
from eth.vm.forks.gray_glacier.computation import GrayGlacierComputation


class ParisComputation(GrayGlacierComputation):
    """
    A class for all execution *message* computations in the ``Paris`` hard fork
    Inherits from :class:`~eth.vm.forks.gray_glacier.GrayGlacierComputation`
    """
    opcodes = PARIS_OPCODES
