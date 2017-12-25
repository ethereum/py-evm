from evm import constants
from evm.exceptions import (
    OutOfGas,
)
from evm.utils.hexadecimal import (
    encode_hex,
)
from evm.utils.keccak import (
    keccak,
)
from ..frontier.state import (
    FrontierVMState,
)


class HomesteadVMState(FrontierVMState):
    def apply_create_message(self, message):
        snapshot = self.snapshot()

        computation = self.apply_message(message)

        if computation.is_error:
            self.revert(snapshot)
            return computation
        else:
            contract_code = computation.output

            if contract_code:
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
                    self.revert(snapshot)
                else:
                    if self.logger:
                        self.logger.debug(
                            "SETTING CODE: %s -> length: %s | hash: %s",
                            encode_hex(message.storage_address),
                            len(contract_code),
                            encode_hex(keccak(contract_code))
                        )

                    with self.state_db() as state_db:
                        state_db.set_code(message.storage_address, contract_code)
                    self.commit(snapshot)
            else:
                self.commit(snapshot)
            return computation
