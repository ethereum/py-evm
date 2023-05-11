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
from eth.vm.forks.paris.computation import (
    ParisComputation,
)

from .constants import (
    INITCODE_WORD_COST,
    MAX_INITCODE_SIZE,
)
from .opcodes import (
    SHANGHAI_OPCODES,
)


class ShanghaiComputation(ParisComputation):
    """
    A class for all execution *message* computations in the ``Shanghai`` hard fork
    """

    opcodes = SHANGHAI_OPCODES

    def __init__(
        self,
        state: StateAPI,
        message: MessageAPI,
        transaction_context: TransactionContextAPI,
    ) -> None:
        super().__init__(state, message, transaction_context)

        # EIP-3651: Warm COINBASE
        self.state.mark_address_warm(self.state.coinbase)

    @classmethod
    def validate_create_message(cls, message: MessageAPI) -> None:
        # EIP-3860: initcode size limit
        initcode_length = len(message.code)

        if initcode_length > MAX_INITCODE_SIZE:
            raise OutOfGas(
                "Contract code size exceeds EIP-3860 limit of "
                f"{MAX_INITCODE_SIZE}. Got code of size: {initcode_length}"
            )

    @classmethod
    def consume_initcode_gas_cost(cls, computation: ComputationAPI) -> None:
        # EIP-3860: initcode gas cost
        initcode_length = len(computation.msg.code)

        initcode_gas_cost = INITCODE_WORD_COST * ceil32(initcode_length) // 32
        computation.consume_gas(
            initcode_gas_cost,
            reason="EIP-3860 initcode cost",
        )
