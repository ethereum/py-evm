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
    AccountDatabaseAPI,
    ComputationAPI,
    MessageAPI,
    SignedTransactionAPI,
    TransactionContextAPI,
    TransactionExecutorAPI,
)
from eth.constants import (
    CREATE_CONTRACT_ADDRESS,
)
from eth.db.account import (
    AccountDB,
)
from eth.exceptions import (
    ContractCreationCollision,
)
from eth.vm.message import (
    Message,
)
from eth.vm.state import (
    BaseState,
    BaseTransactionExecutor,
)

from .computation import (
    FrontierComputation,
)
from .constants import (
    MAX_REFUND_QUOTIENT,
    REFUND_SELFDESTRUCT,
)
from .transaction_context import (
    FrontierTransactionContext,
)
from .validation import (
    validate_frontier_transaction,
)


class FrontierTransactionExecutor(BaseTransactionExecutor):
    def validate_transaction(self, transaction: SignedTransactionAPI) -> None:
        # Validate the transaction
        transaction.validate()
        self.vm_state.validate_transaction(transaction)

    def build_evm_message(self, transaction: SignedTransactionAPI) -> MessageAPI:
        # Use vm_state.get_gas_price instead of transaction_context.gas_price so
        #   that we can run get_transaction_result (aka~ eth_call) and estimate_gas.
        #   Both work better if the GASPRICE opcode returns the original real price,
        #   but the sender's balance doesn't actually deduct the gas. This
        #   get_gas_price() will return 0 for eth_call, but
        #   transaction_context.gas_price will return
        #   the same value as the GASPRICE opcode.
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
            (
                "TRANSACTION: sender: %s | to: %s | value: %s | gas: %s | "
                "gas-price: %s | s: %s | r: %s | y_parity: %s | data-hash: %s"
            ),
            encode_hex(transaction.sender),
            encode_hex(transaction.to),
            transaction.value,
            transaction.gas,
            transaction.gas_price,
            transaction.s,
            transaction.r,
            transaction.y_parity,
            encode_hex(keccak(transaction.data)),
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

    def build_computation(
        self, message: MessageAPI, transaction: SignedTransactionAPI
    ) -> ComputationAPI:
        transaction_context = self.vm_state.get_transaction_context(transaction)
        if message.is_create:
            is_collision = self.vm_state.has_code_or_nonce(message.storage_address)

            if is_collision:
                # The address of the newly created contract has *somehow* collided
                # with an existing contract address.
                computation = self.vm_state.get_computation(
                    message, transaction_context
                )
                computation.error = ContractCreationCollision(
                    f"Address collision while creating contract: "
                    f"{encode_hex(message.storage_address)}"
                )
                self.vm_state.logger.debug2(
                    "Address collision while creating contract: %s",
                    encode_hex(message.storage_address),
                )
            else:
                computation = self.vm_state.computation_class.apply_create_message(
                    self.vm_state,
                    message,
                    transaction_context,
                )
        else:
            computation = self.vm_state.computation_class.apply_message(
                self.vm_state,
                message,
                transaction_context,
            )

        return computation

    @classmethod
    def calculate_gas_refund(cls, computation: ComputationAPI, gas_used: int) -> int:
        # Self Destruct Refunds
        num_deletions = len(computation.get_accounts_for_deletion())
        if num_deletions:
            computation.refund_gas(REFUND_SELFDESTRUCT * num_deletions)

        # Gas Refunds
        gas_refunded = computation.get_gas_refund()

        return min(gas_refunded, gas_used // MAX_REFUND_QUOTIENT)

    def finalize_computation(
        self, transaction: SignedTransactionAPI, computation: ComputationAPI
    ) -> ComputationAPI:
        transaction_context = self.vm_state.get_transaction_context(transaction)

        gas_remaining = computation.get_gas_remaining()
        gas_used = transaction.gas - gas_remaining
        gas_refund = self.calculate_gas_refund(computation, gas_used)
        gas_refund_amount = (gas_refund + gas_remaining) * transaction_context.gas_price

        if gas_refund_amount:
            self.vm_state.logger.debug2(
                "TRANSACTION REFUND: %s -> %s",
                gas_refund_amount,
                encode_hex(computation.msg.sender),
            )
            self.vm_state.delta_balance(computation.msg.sender, gas_refund_amount)

        # Beneficiary Fees
        gas_used = transaction.gas - gas_remaining - gas_refund
        transaction_fee = gas_used * self.vm_state.get_tip(transaction)

        # EIP-161:
        # Even if the txn fee is zero, the coinbase is still touched here. Post-merge,
        # with no block reward, in the cases where the txn fee is also zero, the
        # coinbase may end up zeroed after the computation and thus should be marked
        # for deletion since it was touched.
        self.vm_state.logger.debug2(
            "TRANSACTION FEE: %s -> %s",
            transaction_fee,
            encode_hex(self.vm_state.coinbase),
        )
        self.vm_state.delta_balance(self.vm_state.coinbase, transaction_fee)

        # Process Self Destructs
        for account, _ in computation.get_accounts_for_deletion():
            self.vm_state.logger.debug2("DELETING ACCOUNT: %s", encode_hex(account))
            self.vm_state.delete_account(account)

        return computation


class FrontierState(BaseState):
    computation_class: Type[ComputationAPI] = FrontierComputation
    transaction_context_class: Type[TransactionContextAPI] = FrontierTransactionContext
    account_db_class: Type[AccountDatabaseAPI] = AccountDB
    transaction_executor_class: Type[
        TransactionExecutorAPI
    ] = FrontierTransactionExecutor

    def apply_transaction(self, transaction: SignedTransactionAPI) -> ComputationAPI:
        executor = self.get_transaction_executor()
        return executor(transaction)

    def validate_transaction(self, transaction: SignedTransactionAPI) -> None:
        validate_frontier_transaction(self, transaction)
