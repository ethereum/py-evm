from evm import constants
from evm.exceptions import (
    OutOfGas,
    InsufficientFunds,
    StackDepthLimit,
)
from evm.state import (
    BaseState
)
from evm.utils.hexadecimal import (
    encode_hex,
)
from evm.utils.keccak import (
    keccak,
)


class FrontierState(BaseState):
    def apply_message(self, message):
        snapshot = self.snapshot()

        if message.depth > constants.STACK_DEPTH_LIMIT:
            raise StackDepthLimit("Stack depth limit reached")

        if message.should_transfer_value and message.value:
            with self.state_db() as state_db:
                sender_balance = state_db.get_balance(message.sender)

                if sender_balance < message.value:
                    raise InsufficientFunds(
                        "Insufficient funds: {0} < {1}".format(sender_balance, message.value)
                    )

                state_db.delta_balance(message.sender, -1 * message.value)
                state_db.delta_balance(message.storage_address, message.value)

            self.logger.debug(
                "TRANSFERRED: %s from %s -> %s",
                message.value,
                encode_hex(message.sender),
                encode_hex(message.storage_address),
            )

        with self.state_db() as state_db:
            state_db.touch_account(message.storage_address)

        computation = self.apply_computation(message)

        if computation.is_error:
            self.revert(snapshot)
        else:
            self.commit(snapshot)

        return computation

    def apply_create_message(self, message):
        computation = self.apply_message(message)

        if computation.is_error:
            return computation
        else:
            contract_code = computation.output

            if contract_code:
                contract_code_gas_fee = len(contract_code) * constants.GAS_CODEDEPOSIT
                try:
                    computation.gas_meter.consume_gas(
                        contract_code_gas_fee,
                        reason="Write contract code for CREATE",
                    )
                except OutOfGas:
                    computation.output = b''
                else:
                    self.logger.debug(
                        "SETTING CODE: %s -> length: %s | hash: %s",
                        encode_hex(message.storage_address),
                        len(contract_code),
                        encode_hex(keccak(contract_code))
                    )
                    with self.state_db() as state_db:
                        state_db.set_code(message.storage_address, contract_code)
            return computation
