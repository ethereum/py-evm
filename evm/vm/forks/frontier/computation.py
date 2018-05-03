from eth_hash.auto import keccak

from evm import constants
from evm import precompiles
from evm.vm.computation import (
    BaseComputation
)
from evm.exceptions import (
    OutOfGas,
    InsufficientFunds,
    StackDepthLimit,
)
from evm.utils.address import (
    force_bytes_to_address,
)
from evm.utils.hexadecimal import (
    encode_hex,
)

from .opcodes import FRONTIER_OPCODES

FRONTIER_PRECOMPILES = {
    force_bytes_to_address(b'\x01'): precompiles.ecrecover,
    force_bytes_to_address(b'\x02'): precompiles.sha256,
    force_bytes_to_address(b'\x03'): precompiles.ripemd160,
    force_bytes_to_address(b'\x04'): precompiles.identity,
}


class FrontierComputation(BaseComputation):
    """
    A class for all execution computations in the ``Frontier`` fork.
    Inherits from :class:`~evm.vm.computation.BaseComputation`
    """
    # Override
    opcodes = FRONTIER_OPCODES
    _precompiles = FRONTIER_PRECOMPILES

    def apply_message(self):
        snapshot = self.state.snapshot()

        if self.msg.depth > constants.STACK_DEPTH_LIMIT:
            raise StackDepthLimit("Stack depth limit reached")

        if self.msg.should_transfer_value and self.msg.value:
            sender_balance = self.state.account_db.get_balance(self.msg.sender)

            if sender_balance < self.msg.value:
                raise InsufficientFunds(
                    "Insufficient funds: {0} < {1}".format(sender_balance, self.msg.value)
                )

            self.state.account_db.delta_balance(self.msg.sender, -1 * self.msg.value)
            self.state.account_db.delta_balance(self.msg.storage_address, self.msg.value)

            self.logger.debug(
                "TRANSFERRED: %s from %s -> %s",
                self.msg.value,
                encode_hex(self.msg.sender),
                encode_hex(self.msg.storage_address),
            )

        self.state.account_db.touch_account(self.msg.storage_address)

        computation = self.apply_computation(
            self.state,
            self.msg,
            self.transaction_context,
        )

        if computation.is_error:
            self.state.revert(snapshot)
        else:
            self.state.commit(snapshot)

        return computation

    def apply_create_message(self):
        computation = self.apply_message()

        if computation.is_error:
            return computation
        else:
            contract_code = computation.output

            if contract_code:
                contract_code_gas_fee = len(contract_code) * constants.GAS_CODEDEPOSIT
                try:
                    computation.consume_gas(
                        contract_code_gas_fee,
                        reason="Write contract code for CREATE",
                    )
                except OutOfGas:
                    computation.output = b''
                else:
                    self.logger.debug(
                        "SETTING CODE: %s -> length: %s | hash: %s",
                        encode_hex(self.msg.storage_address),
                        len(contract_code),
                        encode_hex(keccak(contract_code))
                    )
                    self.state.account_db.set_code(self.msg.storage_address, contract_code)
            return computation
