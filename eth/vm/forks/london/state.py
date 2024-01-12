from typing import (
    Type,
)

from eth_hash.auto import (
    keccak,
)
from eth_utils import (
    encode_hex,
)

from eth._utils.address import (
    generate_contract_address,
)
from eth.abc import (
    ComputationAPI,
    MessageAPI,
    SignedTransactionAPI,
    StateAPI,
    TransactionContextAPI,
    TransactionExecutorAPI,
)
from eth.constants import (
    CREATE_CONTRACT_ADDRESS,
)
from eth.vm.forks.berlin.state import (
    BerlinState,
    BerlinTransactionExecutor,
)
from eth.vm.message import (
    Message,
)

from .computation import (
    LondonComputation,
)
from .constants import (
    EIP3529_MAX_REFUND_QUOTIENT,
)
from .validation import (
    validate_london_normalized_transaction,
)


class LondonTransactionExecutor(BerlinTransactionExecutor):
    def build_evm_message(self, transaction: SignedTransactionAPI) -> MessageAPI:
        # Use vm_state.get_gas_price instead of transaction_context.gas_price so
        #   that we can run get_transaction_result (aka~ eth_call) and estimate_gas.
        #   Both work better if the GASPRICE opcode returns the original real price,
        #   but the sender's balance doesn't actually deduct the gas. This
        #   get_gas_price() will return 0 for eth_call, but
        #   transaction_context.gas_price will return the same value as the
        #   GASPRICE opcode.
        gas_fee = transaction.gas * self.vm_state.get_gas_price(transaction)

        # Buy Gas
        self.vm_state.delta_balance(transaction.sender, -1 * gas_fee)

        # Increment Nonce
        self.vm_state.increment_nonce(transaction.sender)

        # Setup VM Message
        message_gas = transaction.gas - transaction.intrinsic_gas

        if transaction.to == CREATE_CONTRACT_ADDRESS:
            contract_address = generate_contract_address(
                transaction.sender,
                self.vm_state.get_nonce(transaction.sender) - 1,
            )
            data = b""
            code = transaction.data
        else:
            contract_address = None
            data = transaction.data
            code = self.vm_state.get_code(transaction.to)

        self.vm_state.logger.debug2(
            f"TRANSACTION: {repr(transaction)}; "
            f"sender: {encode_hex(transaction.sender)} | "
            f"to: {encode_hex(transaction.to)} | "
            f"data-hash: {encode_hex(keccak(transaction.data))}"
        )

        message = Message(
            gas=message_gas,
            to=transaction.to,
            sender=transaction.sender,
            value=transaction.value,
            data=data,
            code=code,
            create_address=contract_address,
        )
        return message

    @classmethod
    def calculate_gas_refund(cls, computation: ComputationAPI, gas_used: int) -> int:
        # Self destruct refunds were added in Frontier
        # London removes them in EIP-3529
        gas_refunded = computation.get_gas_refund()

        return min(gas_refunded, gas_used // EIP3529_MAX_REFUND_QUOTIENT)


class LondonState(BerlinState):
    computation_class = LondonComputation
    transaction_executor_class: Type[TransactionExecutorAPI] = LondonTransactionExecutor

    def get_tip(self, transaction: SignedTransactionAPI) -> int:
        return min(
            transaction.max_fee_per_gas - self.execution_context.base_fee_per_gas,
            transaction.max_priority_fee_per_gas,
        )

    def get_gas_price(self, transaction: SignedTransactionAPI) -> int:
        return min(
            transaction.max_fee_per_gas,
            transaction.max_priority_fee_per_gas
            + self.execution_context.base_fee_per_gas,
        )

    def validate_transaction(self, transaction: SignedTransactionAPI) -> None:
        validate_london_normalized_transaction(
            state=self,
            transaction=transaction,
        )

    def get_transaction_context(
        self: StateAPI, transaction: SignedTransactionAPI
    ) -> TransactionContextAPI:
        """
        London-specific transaction context creation,
        where gas_price includes the block base fee
        """
        effective_gas_price = min(
            transaction.max_priority_fee_per_gas
            + self.execution_context.base_fee_per_gas,
            transaction.max_fee_per_gas,
        )
        # See how this reduces in a pre-1559 transaction:
        # 1. effective_gas_price = min(
        #     transaction.gas_price + self.execution_context.base_fee_per_gas,
        #     transaction.gas_price,
        # )
        # base_fee_per_gas is non-negative, so:
        # 2. effective_gas_price = transaction.gas_price

        return self.get_transaction_context_class()(
            gas_price=effective_gas_price, origin=transaction.sender
        )

    @property
    def base_fee(self: StateAPI) -> int:
        return self.execution_context.base_fee_per_gas
