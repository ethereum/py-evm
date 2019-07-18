from eth_hash.auto import keccak
from eth_utils import (
    encode_hex,
)

from eth import constants
from eth.exceptions import (
    OutOfGas,
)
from eth.vm.computation import BaseComputation
from eth.vm.forks.homestead.computation import (
    HomesteadComputation,
)

from .constants import EIP170_CODE_SIZE_LIMIT
from .opcodes import SPURIOUS_DRAGON_OPCODES


class SpuriousDragonComputation(HomesteadComputation):
    """
    A class for all execution computations in the ``SpuriousDragon`` fork.
    Inherits from :class:`~eth.vm.forks.homestead.computation.HomesteadComputation`
    """
    # Override
    opcodes = SPURIOUS_DRAGON_OPCODES

    def apply_create_message(self) -> BaseComputation:
        snapshot = self.state.snapshot()

        # EIP161 nonce incrementation
        self.state.increment_nonce(self.msg.storage_address)

        computation = self.apply_message()

        if computation.is_error:
            self.state.revert(snapshot)
            return computation
        else:
            contract_code = computation.output

            if contract_code and len(contract_code) >= EIP170_CODE_SIZE_LIMIT:
                computation._error = OutOfGas(
                    "Contract code size exceeds EIP170 limit of {0}.  Got code of "
                    "size: {1}".format(
                        EIP170_CODE_SIZE_LIMIT,
                        len(contract_code),
                    )
                )
                self.state.revert(snapshot)
            elif contract_code:
                contract_code_gas_cost = len(contract_code) * constants.GAS_CODEDEPOSIT
                try:
                    computation.consume_gas(
                        contract_code_gas_cost,
                        reason="Write contract code for CREATE",
                    )
                except OutOfGas as err:
                    # Different from Frontier: reverts state on gas failure while
                    # writing contract code.
                    computation._error = err
                    self.state.revert(snapshot)
                else:
                    if self.logger:
                        self.logger.debug2(
                            "SETTING CODE: %s -> length: %s | hash: %s",
                            encode_hex(self.msg.storage_address),
                            len(contract_code),
                            encode_hex(keccak(contract_code))
                        )

                    self.state.set_code(self.msg.storage_address, contract_code)
                    self.state.commit(snapshot)
            else:
                self.state.commit(snapshot)
            return computation
