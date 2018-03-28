from __future__ import absolute_import
from typing import Type  # noqa: F401

from trie import (
    HexaryTrie,
)

from eth_utils import (
    keccak,
)

from evm import constants
from evm.constants import (
    BLOCK_REWARD,
    UNCLE_DEPTH_PENALTY_FACTOR,
)
from evm.exceptions import (
    ContractCreationCollision,
)
from evm.rlp.logs import (
    Log,
)
from evm.rlp.receipts import (
    Receipt,
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

from .blocks import FrontierBlock
from .computation import FrontierComputation
from .constants import REFUND_SELFDESTRUCT
from .transaction_context import (  # noqa: F401
    BaseTransactionContext,
    FrontierTransactionContext
)
from .validation import validate_frontier_transaction


class FrontierTransactionExecutor(BaseTransactionExecutor):
    def run_pre_computation(self, transaction):
        # Validate the transaction
        transaction.validate()

        self.validate_transaction(transaction)

        gas_fee = transaction.gas * transaction.gas_price
        with self.mutable_state_db() as state_db:
            # Buy Gas
            state_db.delta_balance(transaction.sender, -1 * gas_fee)

            # Increment Nonce
            state_db.increment_nonce(transaction.sender)

            # Setup VM Message
            message_gas = transaction.gas - transaction.intrinsic_gas

            if transaction.to == constants.CREATE_CONTRACT_ADDRESS:
                contract_address = generate_contract_address(
                    transaction.sender,
                    state_db.get_nonce(transaction.sender) - 1,
                )
                data = b''
                code = transaction.data
            else:
                contract_address = None
                data = transaction.data
                code = state_db.get_code(transaction.to)

        self.logger.info(
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

        return Message(
            gas=message_gas,
            to=transaction.to,
            sender=transaction.sender,
            value=transaction.value,
            data=data,
            code=code,
            create_address=contract_address,
        )

    def run_computation(self, transaction, message):
        """Apply the message to the VM."""
        transaction_context = self.get_transaction_context_class()(
            gas_price=transaction.gas_price,
            origin=transaction.sender,
        )
        if message.is_create:
            is_collision = self.read_only_state_db.account_has_code_or_nonce(
                message.storage_address
            )

            if is_collision:
                # The address of the newly created contract has *somehow* collided
                # with an existing contract address.
                computation = self.get_computation(message, transaction_context)
                computation._error = ContractCreationCollision(
                    "Address collision while creating contract: {0}".format(
                        encode_hex(message.storage_address),
                    )
                )
                self.logger.debug(
                    "Address collision while creating contract: %s",
                    encode_hex(message.storage_address),
                )
            else:
                computation = self.get_computation(
                    message,
                    transaction_context,
                ).apply_create_message()
        else:
            computation = self.get_computation(message, transaction_context).apply_message()

        return computation

    def run_post_computation(self, transaction, computation):
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
            self.logger.debug(
                'TRANSACTION REFUND: %s -> %s',
                gas_refund_amount,
                encode_hex(computation.msg.sender),
            )

            with self.mutable_state_db() as state_db:
                state_db.delta_balance(computation.msg.sender, gas_refund_amount)

        # Miner Fees
        transaction_fee = (transaction.gas - gas_remaining - gas_refund) * transaction.gas_price
        self.logger.debug(
            'TRANSACTION FEE: %s -> %s',
            transaction_fee,
            encode_hex(self.coinbase),
        )
        with self.mutable_state_db() as state_db:
            state_db.delta_balance(self.coinbase, transaction_fee)

        # Process Self Destructs
        with self.mutable_state_db() as state_db:
            for account, beneficiary in computation.get_accounts_for_deletion():
                # TODO: need to figure out how we prevent multiple selfdestructs from
                # the same account and if this is the right place to put this.
                self.logger.debug('DELETING ACCOUNT: %s', encode_hex(account))

                # TODO: this balance setting is likely superflous and can be
                # removed since `delete_account` does this.
                state_db.set_balance(account, 0)
                state_db.delete_account(account)

        return computation


def _make_frontier_receipt(state, transaction, computation):
    # Reusable for other forks

    logs = [
        Log(address, topics, data)
        for address, topics, data
        in computation.get_log_entries()
    ]

    gas_remaining = computation.get_gas_remaining()
    gas_refund = computation.get_gas_refund()
    tx_gas_used = (
        transaction.gas - gas_remaining
    ) - min(
        gas_refund,
        (transaction.gas - gas_remaining) // 2,
    )
    gas_used = state.gas_used + tx_gas_used

    receipt = Receipt(
        state_root=state.state_root,
        gas_used=gas_used,
        logs=logs,
    )

    return receipt


class FrontierState(BaseState, FrontierTransactionExecutor):
    block_class = FrontierBlock
    computation_class = FrontierComputation
    trie_class = HexaryTrie
    transaction_context_class = FrontierTransactionContext  # type: Type[BaseTransactionContext]

    def make_receipt(self, transaction, computation):
        receipt = _make_frontier_receipt(self, transaction, computation)
        return receipt

    def validate_transaction(self, transaction):
        validate_frontier_transaction(self, transaction)

    @staticmethod
    def get_block_reward():
        return BLOCK_REWARD

    @staticmethod
    def get_uncle_reward(block_number, uncle):
        return BLOCK_REWARD * (
            UNCLE_DEPTH_PENALTY_FACTOR + uncle.block_number - block_number
        ) // UNCLE_DEPTH_PENALTY_FACTOR

    @classmethod
    def get_nephew_reward(cls):
        return cls.get_block_reward() // 32
