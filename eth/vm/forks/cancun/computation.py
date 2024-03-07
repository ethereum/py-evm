from toolz import (
    merge,
)

from eth._utils.address import (
    force_bytes_to_address,
)
from eth.precompiles.point_evaluation import (
    point_evaluation_precompile,
)
from eth.vm.forks.shanghai.computation import (
    ShanghaiComputation,
)

from .constants import (
    POINT_EVALUATION_PRECOMPILE_ADDRESS,
)
from .opcodes import (
    CANCUN_OPCODES,
)

CANCUN_PRECOMPILES = merge(
    ShanghaiComputation.get_precompiles(),
    {
        force_bytes_to_address(
            POINT_EVALUATION_PRECOMPILE_ADDRESS
        ): point_evaluation_precompile,
    },
)


class CancunComputation(ShanghaiComputation):
    """
    A class for all execution computations in the ``Cancun`` hard fork
    """

    opcodes = CANCUN_OPCODES
    _precompiles = CANCUN_PRECOMPILES
