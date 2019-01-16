from eth_utils.toolz import (
    merge,
)

from eth.vm.forks.byzantium.computation import (
    BYZANTIUM_PRECOMPILES
)
from eth.vm.forks.byzantium.computation import (
    ByzantiumComputation
)
from eth.vm.gas_meter import (
    allow_negative_refund_strategy,
    GasMeter,
)

from .opcodes import CONSTANTINOPLE_OPCODES

CONSTANTINOPLE_PRECOMPILES = merge(
    BYZANTIUM_PRECOMPILES,
    {
        # TODO: add new precompiles
    },
)


class ConstantinopleComputation(ByzantiumComputation):
    """
    A class for all execution computations in the ``Constantinople`` fork.
    Inherits from :class:`~eth.vm.forks.byzantium.computation.ByzantiumComputation`
    """
    # Override
    opcodes = CONSTANTINOPLE_OPCODES
    _precompiles = CONSTANTINOPLE_PRECOMPILES

    def get_gas_meter(self) -> GasMeter:
        return GasMeter(
            self.msg.gas,
            allow_negative_refund_strategy
        )
