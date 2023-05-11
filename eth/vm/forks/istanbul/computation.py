from eth_utils.toolz import (
    merge,
)

from eth import (
    precompiles,
)
from eth._utils.address import (
    force_bytes_to_address,
)
from eth.vm.forks.petersburg.computation import (
    PETERSBURG_PRECOMPILES,
    PetersburgComputation,
)
from eth.vm.gas_meter import (
    GasMeter,
    allow_negative_refund_strategy,
)

from .constants import (
    GAS_ECADD,
    GAS_ECMUL,
    GAS_ECPAIRING_BASE,
    GAS_ECPAIRING_PER_POINT,
)
from .opcodes import (
    ISTANBUL_OPCODES,
)

ISTANBUL_PRECOMPILES = merge(
    PETERSBURG_PRECOMPILES,
    {
        force_bytes_to_address(b"\x06"): precompiles.ecadd(gas_cost=GAS_ECADD),
        force_bytes_to_address(b"\x07"): precompiles.ecmul(gas_cost=GAS_ECMUL),
        force_bytes_to_address(b"\x08"): precompiles.ecpairing(
            gas_cost_base=GAS_ECPAIRING_BASE,
            gas_cost_per_point=GAS_ECPAIRING_PER_POINT,
        ),
        force_bytes_to_address(b"\x09"): precompiles.blake2b_fcompress,
    },
)


class IstanbulComputation(PetersburgComputation):
    """
    A class for all execution *message* computations in the ``Istanbul`` fork.
    Inherits from
    :class:`~eth.vm.forks.constantinople.petersburg.PetersburgComputation`
    """

    # Override
    opcodes = ISTANBUL_OPCODES
    _precompiles = ISTANBUL_PRECOMPILES

    def _configure_gas_meter(self) -> GasMeter:
        return GasMeter(self.msg.gas, allow_negative_refund_strategy)
