from eth_utils import (
    keccak,
)

from evm import constants
from evm.exceptions import (
    OutOfGas,
)
from evm.utils.hexadecimal import (
    encode_hex,
)
from evm.vm.forks.homestead.computation import (
    HomesteadComputation,
)

from .constants import EIP170_CODE_SIZE_LIMIT
from .opcodes import SPURIOUS_DRAGON_OPCODES


class SpuriousDragonComputation(HomesteadComputation):
    # Override
    opcodes = SPURIOUS_DRAGON_OPCODES

    def apply_create_message(self):
        snapshot = self.vm_state.snapshot()

        # EIP161 nonce incrementation
        with self.vm_state.mutable_state_db() as state_db:
            state_db.increment_nonce(self.msg.storage_address)

        computation = self.apply_message()

        if computation.is_error:
            self.vm_state.revert(snapshot)
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
                self.vm_state.revert(snapshot)
            elif contract_code:
                contract_code_gas_cost = len(contract_code) * constants.GAS_CODEDEPOSIT
                try:
                    computation.gas_meter.consume_gas(
                        contract_code_gas_cost,
                        reason="Write contract code for CREATE",
                    )
                except OutOfGas as err:
                    # Different from Frontier: reverts state on gas failure while
                    # writing contract code.
                    computation._error = err
                    self.vm_state.revert(snapshot)
                else:
                    if self.logger:
                        self.logger.debug(
                            "SETTING CODE: %s -> length: %s | hash: %s",
                            encode_hex(self.msg.storage_address),
                            len(contract_code),
                            encode_hex(keccak(contract_code))
                        )

                    with self.vm_state.mutable_state_db() as state_db:
                        state_db.set_code(self.msg.storage_address, contract_code)
                    self.vm_state.commit(snapshot)
            else:
                self.vm_state.commit(snapshot)
            return computation
