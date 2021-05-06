from eth.vm.forks.frontier.constants import REFUND_SELFDESTRUCT
from typing import Type

from eth_hash.auto import keccak
from eth_utils.exceptions import ValidationError
from eth_utils import (
    encode_hex,
)

from eth.abc import (
    AccountDatabaseAPI,
    ComputationAPI,
    MessageAPI,
    SignedTransactionAPI,
    TransactionExecutorAPI,
)
from eth.constants import (
    CREATE_CONTRACT_ADDRESS,
    SECPK1_N,
)
from eth.db.account import (
    AccountDB
)
from eth.vm.message import (
    Message,
)
from eth.vm.forks.berlin.state import (
    BerlinState,
    BerlinTransactionExecutor,
)
from eth.vm.forks.london.blocks import (
    LondonBlockHeader,
)

from eth._utils.address import (
    generate_contract_address,
)

from .computation import LondonComputation
from .transactions import LondonNormalizedTransaction, LondonTypedTransaction, normalize_transaction
from .validation import LondonValidatedTransaction, validate_london_normalized_transaction


class LondonTransactionExecutor(BerlinTransactionExecutor):
    def __call__(
        self,
        transaction: SignedTransactionAPI,
        effective_gas_price: int
    ) -> ComputationAPI:
        # unlike other VMs, don't validate tx here -- we need access to both header and state
        message = self.build_evm_message(transaction, effective_gas_price)
        computation = self.build_computation(message, transaction)
        finalized_computation = self.finalize_computation(
            transaction, computation, effective_gas_price
        )

        return finalized_computation

    def build_evm_message(
        self,
        transaction: LondonValidatedTransaction
    ) -> MessageAPI:
        # Buy Gas
        self.vm_state.delta_balance(
            transaction.sender,
            -1 * transaction.gas * transaction.effective_gas_price
        )

        # Increment Nonce
        self.vm_state.increment_nonce(transaction.sender)

        # Setup VM Message
        message_gas = transaction.gas - transaction.intrinsic_gas

        if transaction.to == CREATE_CONTRACT_ADDRESS:
            contract_address = generate_contract_address(
                transaction.sender,
                self.vm_state.get_nonce(transaction.sender) - 1,
            )
            data = b''
            code = transaction.data
        else:
            contract_address = None
            data = transaction.data
            code = self.vm_state.get_code(transaction.to)

        self.vm_state.logger.debug2(
            (
                "TRANSACTION: sender: %s | to: %s | value: %s | gas: %s | "
                "max_priority_fee_per_gas: %s | max_fee_per_gas: %s | s: %s | "
                "r: %s | y_parity: %s | data-hash: %s"
            ),
            encode_hex(transaction.sender),
            encode_hex(transaction.to),
            transaction.value,
            transaction.gas,
            transaction.max_priority_fee_per_gas,
            transaction.max_fee_per_gas,
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

    def finalize_computation(
            self,
            transaction: LondonValidatedTransaction,
            computation: ComputationAPI
    ) -> ComputationAPI:
        # Self Destruct Refunds
        num_deletions = len(computation.get_accounts_for_deletion())
        if num_deletions:
            computation.refund_gas(REFUND_SELFDESTRUCT * num_deletions)

        # Gas Refunds
        gas_remaining = computation.get_gas_remaining()
        gas_refunded = computation.get_gas_refund()
        gas_used = transaction.gas - gas_remaining
        gas_refund = min(gas_refunded, gas_used // 2)
        gas_refund_amount = (gas_refund + gas_remaining) * transaction.effective_gas_price

        if gas_refund_amount:
            self.vm_state.logger.debug2(
                'TRANSACTION REFUND: %s -> %s',
                gas_refund_amount,
                encode_hex(computation.msg.sender),
            )

            self.vm_state.delta_balance(computation.msg.sender, gas_refund_amount)

        # Miner Fees
        transaction_fee = \
            (transaction.gas - gas_remaining - gas_refund) * transaction.priority_fee_per_gas
        self.vm_state.logger.debug2(
            'TRANSACTION FEE: %s -> %s',
            transaction_fee,
            encode_hex(self.vm_state.coinbase),
        )
        self.vm_state.delta_balance(self.vm_state.coinbase, transaction_fee)

        # Process Self Destructs
        for account, _ in computation.get_accounts_for_deletion():
            # TODO: need to figure out how we prevent multiple selfdestructs from
            # the same account and if this is the right place to put this.
            self.vm_state.logger.debug2('DELETING ACCOUNT: %s', encode_hex(account))

            # TODO: this balance setting is likely superflous and can be
            # removed since `delete_account` does this.
            self.vm_state.set_balance(account, 0)
            self.vm_state.delete_account(account)



        return computation

class LondonState(BerlinState):
    account_db_class: Type[AccountDatabaseAPI] = AccountDB
    computation_class = LondonComputation
    transaction_executor_class: Type[TransactionExecutorAPI] = LondonTransactionExecutor

    def apply_transaction(
            self,
            transaction: SignedTransactionAPI,
            header: LondonBlockHeader
        ) -> ComputationAPI:

        validated_transaction = self.validate_transaction(transaction, header)
        executor = self.get_transaction_executor()
        return executor(validated_transaction)

    def validate_transaction(
        self,
        transaction: SignedTransactionAPI,
        header: LondonBlockHeader
    ) -> LondonValidatedTransaction:

        # homestead validation
        if transaction.s > SECPK1_N // 2 or transaction.s == 0:
            raise ValidationError("Invalid signature S value")

        normalized_transaction = normalize_transaction(transaction)
        validated_transaction = validate_london_normalized_transaction(
            state=self, transaction=normalized_transaction, header=header
        )
        return validated_transaction

    def get_transaction_context(cls,
                                transaction: LondonNormalizedTransaction) -> TransactionContextAPI:
        
