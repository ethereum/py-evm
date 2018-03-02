from eth_utils import (
    keccak,
)

from evm.constants import (
    STACK_DEPTH_LIMIT,
)
from evm.exceptions import (
    OutOfGas,
    InsufficientFunds,
    StackDepthLimit,
    GasPriceAlreadySet,
    NotTopLevelCall,
)
from evm.vm.message import (
    ShardingMessage,
)
from evm.utils.hexadecimal import (
    encode_hex,
)
from evm.validation import (
    validate_uint256,
)

from evm.vm.forks.byzantium.computation import (
    ByzantiumComputation,
)
from evm.vm.forks.spurious_dragon.constants import (
    EIP170_CODE_SIZE_LIMIT,
    GAS_CODEDEPOSIT,
)

from .opcodes import SHARDING_OPCODES


class ShardingComputation(ByzantiumComputation):
    _paygas_gasprice = None

    # Override
    opcodes = SHARDING_OPCODES

    def get_PAYGAS_gas_price(self):
        return self._paygas_gasprice

    def set_PAYGAS_gasprice(self, gas_price):
        validate_uint256(gas_price, title="PAYGAY.gas_price")
        if self.msg.depth != 0:
            raise NotTopLevelCall(
                "The `set_PAYGAS_gasprice` API is only valid when"
                "called from the top level computation"
            )

        if self._paygas_gasprice is None:
            self._paygas_gasprice = gas_price
        else:
            raise GasPriceAlreadySet(
                "PAYGAS is already triggered once with gas price: {}".format(self._paygas_gasprice)
            )

    def compute_transaction_fee_and_refund(self):
        gas_price = self.get_PAYGAS_gas_price()
        if gas_price is None:
            gas_price = 0

        transaction_gas = self.transaction_context.transaction_gas_limit
        gas_remaining = self.get_gas_remaining()
        gas_refunded = self.get_gas_refund()
        gas_used = transaction_gas - gas_remaining
        gas_refund = min(gas_refunded, gas_used // 2)
        gas_refund_amount = (gas_refund + gas_remaining) * gas_price
        tx_fee = (transaction_gas - gas_remaining - gas_refund) * gas_price
        return tx_fee, gas_refund_amount

    def apply_message(self):
        snapshot = self.vm_state.snapshot()

        if self.msg.depth > STACK_DEPTH_LIMIT:
            raise StackDepthLimit("Stack depth limit reached")

        if self.msg.should_transfer_value and self.msg.value:
            with self.state_db() as state_db:
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

        computation = self.apply_computation(
            self.vm_state,
            self.msg,
            self.transaction_context,
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

                    with self.state_db() as state_db:
                        state_db.set_code(self.msg.storage_address, contract_code)
                    self.vm_state.commit(snapshot)
            else:
                self.vm_state.commit(snapshot)
            return computation

    def prepare_child_message(self, gas, to, value, data, code, **kwargs):
        kwargs.setdefault('sender', self.msg.storage_address)

        child_message = ShardingMessage(
            gas=gas,
            to=to,
            value=value,
            data=data,
            code=code,
            depth=self.msg.depth + 1,
            access_list=self.msg.access_list,
            **kwargs
        )
        return child_message
