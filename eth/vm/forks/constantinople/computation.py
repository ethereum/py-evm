from eth.vm.forks.byzantium.computation import (
    BYZANTIUM_PRECOMPILES,
    ByzantiumComputation,
)
from eth.vm.gas_meter import (
    GasMeter,
    allow_negative_refund_strategy,
)

from .opcodes import (
    CONSTANTINOPLE_OPCODES,
)

CONSTANTINOPLE_PRECOMPILES = BYZANTIUM_PRECOMPILES


class ConstantinopleComputation(ByzantiumComputation):
    """
    A class for all execution *message* computations in the ``Constantinople`` fork.
    Inherits from
    :class:`~eth.vm.forks.byzantium.computation.ByzantiumComputation`
    """

    # Override
    opcodes = CONSTANTINOPLE_OPCODES
    _precompiles = CONSTANTINOPLE_PRECOMPILES

    def _configure_gas_meter(self) -> GasMeter:
        return GasMeter(self.msg.gas, allow_negative_refund_strategy)
