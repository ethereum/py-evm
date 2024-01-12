from eth._utils.numeric import (
    ceil32,
)
from eth.abc import (
    ComputationAPI,
    MessageAPI,
    StateAPI,
    TransactionContextAPI,
)
from eth.exceptions import (
    OutOfGas,
)
from eth.vm.forks.shanghai.computation import (
    ShanghaiComputation,
)

from .opcodes import (
    CANCUN_OPCODES,
)


class CancunComputation(ShanghaiComputation):
    """
    A class for all execution computations in the ``Cancun`` hard fork
    """

    opcodes = CANCUN_OPCODES
