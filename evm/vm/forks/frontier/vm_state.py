from __future__ import absolute_import
import rlp

from evm import constants
from evm.constants import (
    GAS_LIMIT_ADJUSTMENT_FACTOR,
    GAS_LIMIT_MAXIMUM,
    GAS_LIMIT_MINIMUM,
    MAX_UNCLES,
)
from evm.exceptions import (
    BlockNotFound,
    ContractCreationCollision,
    ValidationError,
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
from evm.utils.keccak import (
    keccak,
)
from evm.validation import (
    validate_length_lte,
)

from .computation import FrontierComputation
from .constants import REFUND_SELFDESTRUCT
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
    with vm_state.state_db() as state_db:
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
        gas_price=transaction.gas_price,
        to=transaction.to,
        sender=transaction.sender,
        value=transaction.value,
        data=data,
        code=code,
        create_address=contract_address,
    )

    #
    # 2) Apply the message to the VM.
    #
    if message.is_create:
        with vm_state.state_db(read_only=True) as state_db:
            is_collision = state_db.account_has_code_or_nonce(contract_address)

        if is_collision:
            # The address of the newly created contract has *somehow* collided
            # with an existing contract address.
            computation = vm_state.get_computation(message)
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
            computation = vm_state.get_computation(message).apply_create_message()
    else:
        computation = vm_state.get_computation(message).apply_message()

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

        with vm_state.state_db() as state_db:
            state_db.delta_balance(message.sender, gas_refund_amount)

    # Miner Fees
    transaction_fee = (transaction.gas - gas_remaining - gas_refund) * transaction.gas_price
    vm_state.logger.debug(
        'TRANSACTION FEE: %s -> %s',
        transaction_fee,
        encode_hex(vm_state.coinbase),
    )
    with vm_state.state_db() as state_db:
        state_db.delta_balance(vm_state.coinbase, transaction_fee)

    # Process Self Destructs
    with vm_state.state_db() as state_db:
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

    gas_used = vm_state.block_header.gas_used + tx_gas_used

    receipt = Receipt(
        state_root=vm_state.block_header.state_root,
        gas_used=gas_used,
        logs=logs,
    )

    return receipt


class FrontierVMState(BaseVMState):
    computation_class = FrontierComputation

    def execute_transaction(self, transaction):
        computation = _execute_frontier_transaction(self, transaction)
        return computation, self.block_header

    def make_receipt(self, transaction, computation):
        receipt = _make_frontier_receipt(self, transaction, computation)
        return receipt

    def validate_block(self, block):
        if not block.is_genesis:
            parent_header = self.parent_header

            self._validate_gas_limit(block)
            validate_length_lte(block.header.extra_data, 32, title="BlockHeader.extra_data")

            # timestamp
            if block.header.timestamp < parent_header.timestamp:
                raise ValidationError(
                    "`timestamp` is before the parent block's timestamp.\n"
                    "- block  : {0}\n"
                    "- parent : {1}. ".format(
                        block.header.timestamp,
                        parent_header.timestamp,
                    )
                )
            elif block.header.timestamp == parent_header.timestamp:
                raise ValidationError(
                    "`timestamp` is equal to the parent block's timestamp\n"
                    "- block : {0}\n"
                    "- parent: {1}. ".format(
                        block.header.timestamp,
                        parent_header.timestamp,
                    )
                )

        if len(block.uncles) > MAX_UNCLES:
            raise ValidationError(
                "Blocks may have a maximum of {0} uncles.  Found "
                "{1}.".format(MAX_UNCLES, len(block.uncles))
            )

        for uncle in block.uncles:
            self.validate_uncle(block, uncle)

        if not self.is_key_exists(block.header.state_root):
            raise ValidationError(
                "`state_root` was not found in the db.\n"
                "- state_root: {0}".format(
                    block.header.state_root,
                )
            )
        local_uncle_hash = keccak(rlp.encode(block.uncles))
        if local_uncle_hash != block.header.uncles_hash:
            raise ValidationError(
                "`uncles_hash` and block `uncles` do not match.\n"
                " - num_uncles       : {0}\n"
                " - block uncle_hash : {1}\n"
                " - header uncle_hash: {2}".format(
                    len(block.uncles),
                    local_uncle_hash,
                    block.header.uncle_hash,
                )
            )

    def _validate_gas_limit(self, block):
        gas_limit = block.header.gas_limit
        if gas_limit < GAS_LIMIT_MINIMUM:
            raise ValidationError("Gas limit {0} is below minimum {1}".format(
                gas_limit, GAS_LIMIT_MINIMUM))
        if gas_limit > GAS_LIMIT_MAXIMUM:
            raise ValidationError("Gas limit {0} is above maximum {1}".format(
                gas_limit, GAS_LIMIT_MAXIMUM))
        parent_gas_limit = self.parent_header.gas_limit
        diff = gas_limit - parent_gas_limit
        if diff > (parent_gas_limit // GAS_LIMIT_ADJUSTMENT_FACTOR):
            raise ValidationError(
                "Gas limit {0} difference to parent {1} is too big {2}".format(
                    gas_limit, parent_gas_limit, diff))

    def validate_uncle(self, block, uncle):
        if uncle.block_number >= block.number:
            raise ValidationError(
                "Uncle number ({0}) is higher than block number ({1})".format(
                    uncle.block_number, block.number))
        try:
            parent_header = self.get_block_header_by_hash(uncle.parent_hash)
        except BlockNotFound:
            raise ValidationError(
                "Uncle ancestor not found: {0}".format(uncle.parent_hash))
        if uncle.block_number != parent_header.block_number + 1:
            raise ValidationError(
                "Uncle number ({0}) is not one above ancestor's number ({1})".format(
                    uncle.block_number, parent_header.block_number))
        if uncle.timestamp < parent_header.timestamp:
            raise ValidationError(
                "Uncle timestamp ({0}) is before ancestor's timestamp ({1})".format(
                    uncle.timestamp, parent_header.timestamp))
        if uncle.gas_used > uncle.gas_limit:
            raise ValidationError(
                "Uncle's gas usage ({0}) is above the limit ({1})".format(
                    uncle.gas_used, uncle.gas_limit))

    def validate_transaction(self, transaction):
        validate_frontier_transaction(self, transaction)
