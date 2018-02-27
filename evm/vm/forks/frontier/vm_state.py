from __future__ import absolute_import

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
from evm.vm_state import (
    BaseVMState,
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
from .transaction_context import FrontierTransactionContext
from .validation import validate_frontier_transaction


def _execute_frontier_transaction(vm_state, transaction):
    # Reusable for other forks

    #
    # 1) Pre Computation
    #

    # Validate the transaction
    transaction.validate()

    vm_state.validate_transaction(transaction)

    gas_fee = transaction.gas * transaction.gas_price
    with vm_state.mutable_state_db() as state_db:
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

    vm_state.logger.info(
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
    transaction_context = vm_state.get_transaction_context_class()(
        gas_price=transaction.gas_price,
        origin=transaction.sender,
    )

    #
    # 2) Apply the message to the VM.
    #
    if message.is_create:
        is_collision = vm_state.read_only_state_db.account_has_code_or_nonce(contract_address)

        if is_collision:
            # The address of the newly created contract has *somehow* collided
            # with an existing contract address.
            computation = vm_state.get_computation(message, transaction_context)
            computation._error = ContractCreationCollision(
                "Address collision while creating contract: {0}".format(
                    encode_hex(contract_address),
                )
            )
            vm_state.logger.debug(
                "Address collision while creating contract: %s",
                encode_hex(contract_address),
            )
        else:
            computation = vm_state.get_computation(
                message,
                transaction_context,
            ).apply_create_message()
    else:
        computation = vm_state.get_computation(message, transaction_context).apply_message()

    #
    # 2) Post Computation
    #
    # Self Destruct Refunds
    num_deletions = len(computation.get_accounts_for_deletion())
    if num_deletions:
        computation.gas_meter.refund_gas(REFUND_SELFDESTRUCT * num_deletions)

    # Gas Refunds
    gas_remaining = computation.get_gas_remaining()
    gas_refunded = computation.get_gas_refund()
    gas_used = transaction.gas - gas_remaining
    gas_refund = min(gas_refunded, gas_used // 2)
    gas_refund_amount = (gas_refund + gas_remaining) * transaction.gas_price

    if gas_refund_amount:
        vm_state.logger.debug(
            'TRANSACTION REFUND: %s -> %s',
            gas_refund_amount,
            encode_hex(message.sender),
        )

        with vm_state.mutable_state_db() as state_db:
            state_db.delta_balance(message.sender, gas_refund_amount)

    # Miner Fees
    transaction_fee = (transaction.gas - gas_remaining - gas_refund) * transaction.gas_price
    vm_state.logger.debug(
        'TRANSACTION FEE: %s -> %s',
        transaction_fee,
        encode_hex(vm_state.coinbase),
    )
    with vm_state.mutable_state_db() as state_db:
        state_db.delta_balance(vm_state.coinbase, transaction_fee)

    # Process Self Destructs
    with vm_state.mutable_state_db() as state_db:
        for account, beneficiary in computation.get_accounts_for_deletion():
            # TODO: need to figure out how we prevent multiple selfdestructs from
            # the same account and if this is the right place to put this.
            vm_state.logger.debug('DELETING ACCOUNT: %s', encode_hex(account))

            # TODO: this balance setting is likely superflous and can be
            # removed since `delete_account` does this.
            state_db.set_balance(account, 0)
            state_db.delete_account(account)

    return computation


def _make_frontier_receipt(vm_state, transaction, computation):
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
    gas_used = vm_state.gas_used + tx_gas_used

    receipt = Receipt(
        state_root=vm_state.state_root,
        gas_used=gas_used,
        logs=logs,
    )

    return receipt


class FrontierVMState(BaseVMState):
    block_class = FrontierBlock
    computation_class = FrontierComputation
    trie_class = HexaryTrie
    transaction_context_class = FrontierTransactionContext

    def execute_transaction(self, transaction):
        computation = _execute_frontier_transaction(self, transaction)
        return computation

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
