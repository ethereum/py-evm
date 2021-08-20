from eth.vm.forks.berlin.computation import (
    BerlinComputation,
)

from .opcodes import LONDON_OPCODES


class LondonComputation(BerlinComputation):
    """
    A class for all execution computations in the ``London`` fork.
    Inherits from :class:`~eth.vm.forks.berlin.BerlinComputation`
    """
    opcodes = LONDON_OPCODES
