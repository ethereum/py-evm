from evm.constants import (
    STACK_DEPTH_LIMIT,
)
from evm.exceptions import (
    OutOfGas,
    InsufficientFunds,
    StackDepthLimit,
)
from evm.utils.hexadecimal import (
    encode_hex,
)
from evm.utils.keccak import (
    keccak,
)

from ..spurious_dragon.computation import (
    SpuriousDragonComputation,
)
from ..spurious_dragon.constants import (
    EIP170_CODE_SIZE_LIMIT,
    GAS_CODEDEPOSIT,
)


class ShardingComputation(SpuriousDragonComputation):
    def apply_message(self):
        snapshot = self.vm_state.snapshot()

        if self.msg.depth > STACK_DEPTH_LIMIT:
            raise StackDepthLimit("Stack depth limit reached")

        if self.msg.should_transfer_value and self.msg.value:
            with self.vm_state.state_db() as state_db:
                sender_balance = state_db.get_balance(self.msg.sender)

                if sender_balance < self.msg.value:
                    raise InsufficientFunds(
                        "Insufficient funds: {0} < {1}".format(sender_balance, self.msg.value)
                    )

                state_db.delta_balance(self.msg.sender, -1 * self.msg.value)
                state_db.delta_balance(self.msg.storage_address, self.msg.value)

            self.logger.debug(
                "TRANSFERRED: %s from %s -> %s",
                self.msg.value,
                encode_hex(self.msg.sender),
                encode_hex(self.msg.storage_address),
            )

        with self.vm_state.state_db() as state_db:
            state_db.touch_account(self.msg.storage_address)

        computation = self.apply_computation(
            self.vm_state,
            self.msg,
            self.opcodes,
            self.precompiles,
        )

        if computation.is_error:
            self.vm_state.revert(snapshot)
        else:
            self.vm_state.commit(snapshot)

        return computation

    def apply_create_message(self):
        # Remove EIP160 nonce increment but keep EIP170 contract code size limit
        snapshot = self.vm_state.snapshot()

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
                contract_code_gas_cost = len(contract_code) * GAS_CODEDEPOSIT
                try:
                    computation.gas_meter.consume_gas(
                        contract_code_gas_cost,
                        reason="Write contract code for CREATE2",
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

                    with self.vm_state.state_db() as state_db:
                        state_db.set_code(self.msg.storage_address, contract_code)
                    self.vm_state.commit(snapshot)
            else:
                self.vm_state.commit(snapshot)
            return computation
