from .opcodes import PARIS_OPCODES
from eth.vm.forks.gray_glacier.computation import GrayGlacierComputation


class ParisComputation(GrayGlacierComputation):
    """
    A class for all execution computations in the ``Paris`` hard fork
    (a.k.a. "The Merge").
    Inherits from :class:`~eth.vm.forks.gray_glacier.GrayGlacierComputation`
    """
    opcodes = PARIS_OPCODES
