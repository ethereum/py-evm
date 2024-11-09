from eth.vm.forks.cancun.computation import (
    CancunComputation,
)
from eth.vm.forks.prague.opcodes import (
    PRAGUE_OPCODES,
)


class PragueComputation(CancunComputation):
    """
    A class for all execution computations in the ``Prague`` hard fork
    """

    opcodes = PRAGUE_OPCODES
