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
from evm.vm.forks.frontier.computation import (
    FrontierComputation,
)

from .opcodes import HOMESTEAD_OPCODES


class HomesteadComputation(FrontierComputation):
    # Override
    opcodes = HOMESTEAD_OPCODES

    def apply_create_message(self):
        snapshot = self.state.snapshot()

        computation = self.apply_message()

        if computation.is_error:
            self.state.revert(snapshot)
            return computation
        else:
            contract_code = computation.output

            if contract_code:
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
                        self.logger.debug(
                            "SETTING CODE: %s -> length: %s | hash: %s",
                            encode_hex(self.msg.storage_address),
                            len(contract_code),
                            encode_hex(keccak(contract_code))
                        )

                    with self.state.mutable_state_db() as state_db:
                        state_db.set_code(self.msg.storage_address, contract_code)
                    self.state.commit(snapshot)
            else:
                self.state.commit(snapshot)
            return computation
