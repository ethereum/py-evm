from __future__ import absolute_import
from typing import Type  # noqa: F401

from eth_hash.auto import keccak

from evm import constants
from evm.db.account import (
    AccountDB,
)
from evm.exceptions import (
    ContractCreationCollision,
    ValidationError,
)
from evm.vm.message import (
    Message,
)
from evm.vm.state import (
    BaseState,
    BaseTransactionExecutor,
)

from evm.utils.address import (
    generate_contract_address,
)
from evm.utils.hexadecimal import (
    encode_hex,
)

from .computation import FrontierComputation
from .constants import REFUND_SELFDESTRUCT
from .transaction_context import (  # noqa: F401
    BaseTransactionContext,
    FrontierTransactionContext
)
from .validation import validate_frontier_transaction


class FrontierTransactionExecutor(BaseTransactionExecutor):

    def validate_transaction(self, transaction):

        # Validate the transaction

        if transaction.intrinsic_gas > transaction.gas:
            raise ValidationError("Insufficient gas")

        transaction.validate()
        self.vm_state.validate_transaction(transaction)

        return transaction

    def build_evm_message(self, transaction):

        transaction_context = self.get_transaction_context(transaction)
        gas_fee = transaction.gas * transaction_context.gas_price

        # Buy Gas
        self.vm_state.account_db.delta_balance(transaction.sender, -1 * gas_fee)

        # Increment Nonce
        self.vm_state.account_db.increment_nonce(transaction.sender)

        # Setup VM Message
        message_gas = transaction.gas - transaction.intrinsic_gas

        if transaction.to == constants.CREATE_CONTRACT_ADDRESS:
            contract_address = generate_contract_address(
                transaction.sender,
                self.vm_state.account_db.get_nonce(transaction.sender) - 1,
            )
            data = b''
            code = transaction.data
        else:
            contract_address = None
            data = transaction.data
            code = self.vm_state.account_db.get_code(transaction.to)

        self.vm_state.logger.debug(
            (
                "TRANSACTION: sender: %s | to: %s | value: %s | gas: %s | "
                "gas-price: %s | s: %s | r: %s | v: %s | data-hash: %s"
            ),
            encode_hex(transaction.sender),
            encode_hex(transaction.to),
            transaction.value,
            transaction.gas,
            transaction.gas_price,
            transaction.s,
            transaction.r,
            transaction.v,
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

    def build_computation(self, message, transaction):
        """Apply the message to the VM."""
        transaction_context = self.get_transaction_context(transaction)
        if message.is_create:
            is_collision = self.vm_state.account_db.account_has_code_or_nonce(
                message.storage_address
            )

            if is_collision:
                # The address of the newly created contract has *somehow* collided
                # with an existing contract address.
                computation = self.vm_state.get_computation(message, transaction_context)
                computation._error = ContractCreationCollision(
                    "Address collision while creating contract: {0}".format(
                        encode_hex(message.storage_address),
                    )
                )
                self.vm_state.logger.debug(
                    "Address collision while creating contract: %s",
                    encode_hex(message.storage_address),
                )
            else:
                computation = self.vm_state.get_computation(
                    message,
                    transaction_context,
                ).apply_create_message()
        else:
            computation = self.vm_state.get_computation(
                message,
                transaction_context).apply_message()

        return computation

    def finalize_computation(self, transaction, computation):
        # Self Destruct Refunds
        num_deletions = len(computation.get_accounts_for_deletion())
        if num_deletions:
            computation.refund_gas(REFUND_SELFDESTRUCT * num_deletions)

        # Gas Refunds
        gas_remaining = computation.get_gas_remaining()
        gas_refunded = computation.get_gas_refund()
        gas_used = transaction.gas - gas_remaining
        gas_refund = min(gas_refunded, gas_used // 2)
        gas_refund_amount = (gas_refund + gas_remaining) * transaction.gas_price

        if gas_refund_amount:
            self.vm_state.logger.debug(
                'TRANSACTION REFUND: %s -> %s',
                gas_refund_amount,
                encode_hex(computation.msg.sender),
            )

            self.vm_state.account_db.delta_balance(computation.msg.sender, gas_refund_amount)

        # Miner Fees
        transaction_fee = \
            (transaction.gas - gas_remaining - gas_refund) * transaction.gas_price
        self.vm_state.logger.debug(
            'TRANSACTION FEE: %s -> %s',
            transaction_fee,
            encode_hex(self.vm_state.coinbase),
        )
        self.vm_state.account_db.delta_balance(self.vm_state.coinbase, transaction_fee)

        # Process Self Destructs
        for account, beneficiary in computation.get_accounts_for_deletion():
            # TODO: need to figure out how we prevent multiple selfdestructs from
            # the same account and if this is the right place to put this.
            self.vm_state.logger.debug('DELETING ACCOUNT: %s', encode_hex(account))

            # TODO: this balance setting is likely superflous and can be
            # removed since `delete_account` does this.
            self.vm_state.account_db.set_balance(account, 0)
            self.vm_state.account_db.delete_account(account)

        return computation


class FrontierState(BaseState):
    computation_class = FrontierComputation
    transaction_context_class = FrontierTransactionContext  # type: Type[BaseTransactionContext]
    account_db_class = AccountDB  # Type[BaseAccountDB]
    transaction_executor = FrontierTransactionExecutor  # Type[BaseTransactionExecutor]

    def validate_transaction(self, transaction):
        validate_frontier_transaction(self.account_db, transaction)

    def execute_transaction(self, transaction):
        executor = self.get_transaction_executor()
        return executor(transaction)
