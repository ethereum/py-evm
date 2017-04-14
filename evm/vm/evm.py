import logging

from evm import constants
from evm import opcode_values
from evm.precompile import (
    PRECOMPILES,
)
from evm.logic.invalid import (
    InvalidOpcode,
)
from evm.exceptions import (
    OutOfGas,
    InsufficientFunds,
    StackDepthLimit,
)

from evm.utils.keccak import (
    keccak,
)
from evm.utils.address import (
    generate_contract_address,
)

from .message import (
    Message,
)
from .computation import (
    Computation,
)


BREAK_OPCODES = {
    opcode_values.RETURN,
    opcode_values.STOP,
    opcode_values.SUICIDE,
}


def _apply_transaction(evm, transaction):
    # Increment Nonce
    evm.block.state_db.increment_nonce(transaction.sender)

    # Buy Gas
    gas_cost = transaction.gas * transaction.gas_price
    sender_balance = evm.block.state_db.get_balance(transaction.sender)
    if sender_balance < gas_cost:
        raise InsufficientFunds("Sender account balance cannot afford txn gas")
    evm.block.state_db.set_balance(transaction.sender, sender_balance - gas_cost)

    message_gas = transaction.gas - transaction.intrensic_gas

    if transaction.to == constants.ZERO_ADDRESS:
        contract_address = generate_contract_address(
            transaction.sender,
            evm.block.state_db.get_nonce(transaction.sender) - 1,
        )
    else:
        contract_address = None

    message = Message(
        gas=message_gas,
        gas_price=transaction.gas_price,
        to=transaction.to,
        sender=transaction.sender,
        value=transaction.value,
        data=transaction.data,
        create_address=contract_address,
    )

    if message.is_create:
        computation = evm.apply_create_message(message)
    else:
        computation = evm.apply_message(message)

    if computation.error:
        # Miner Fees
        transaction_fee = transaction.gas * transaction.gas_price
        coinbase_balance = evm.block.state_db.get_balance(evm.block.header.coinbase)
        evm.block.state_db.set_balance(evm.block.header.coinbase, coinbase_balance + transaction_fee)
    else:
        # Suicide Refunds
        num_deletions = len(computation.get_accounts_for_deletion())
        if num_deletions:
            computation.gas_meter.refund_gas(constants.REFUND_SUICIDE * num_deletions)

        # Gas Refunds
        gas_remaining = computation.gas_meter.gas_remaining
        gas_refunded = computation.get_gas_refund()
        gas_used = transaction.gas - gas_remaining
        gas_refund = min(gas_refunded, gas_used // 2)
        gas_refund_amount = (gas_refund + gas_remaining) * transaction.gas_price

        if evm.logger:
            evm.logger.debug('TRANSACTION REFUND: %s', gas_refund)

        sender_balance = evm.block.state_db.get_balance(message.sender)
        evm.block.state_db.set_balance(message.sender, sender_balance + gas_refund_amount)

        # Miner Fees
        transaction_fee = (transaction.gas - gas_remaining - gas_refund) * transaction.gas_price
        if evm.logger:
            evm.logger.debug('TRANSACTION FEE: %s', transaction_fee)
        coinbase_balance = evm.block.state_db.get_balance(evm.block.header.coinbase)
        evm.block.state_db.set_balance(evm.block.header.coinbase, coinbase_balance + transaction_fee)

    # Suicides
    for account, beneficiary in computation.get_accounts_for_deletion():
        # TODO: need to figure out how we prevent multiple suicides from
        # the same account and if this is the right place to put this.
        if evm.logger is not None:
            evm.logger.debug('DELETING ACCOUNT: %s', account)

        evm.block.state_db.set_balance(account, 0)
        evm.block.state_db.delete_account(account)

    return computation


def _apply_create_message(evm, message):
    snapshot = evm.snapshot()

    if evm.block.state_db.account_exists(message.storage_address):
        evm.block.state_db.set_nonce(message.storage_address, 0)
        evm.block.state_db.set_code(message.storage_address, b'')
        evm.block.state_db.delete_storage(message.storage_address)

    computation = evm.apply_message(message)

    if message.sender != message.origin:
        evm.block.state_db.increment_nonce(computation.msg.sender)

    if computation.error:
        return computation
    else:
        contract_code = computation.output
        if contract_code:
            contract_code_gas_cost = len(contract_code) * constants.GAS_CODEDEPOSIT
            try:
                computation.gas_meter.consume_gas(
                    contract_code_gas_cost,
                    reason="Write contract code for CREATE",
                )
            except OutOfGas as err:
                evm.revert(snapshot)
                computation.error = err
            else:
                if evm.logger:
                    evm.logger.debug(
                        "SETTING CODE: %s -> %s",
                        message.storage_address,
                        keccak(contract_code),
                    )
                computation.evm.block.state_db.set_code(message.storage_address, contract_code)
        return computation


def _apply_message(evm, message):
    snapshot = evm.snapshot()

    if message.depth > constants.STACK_DEPTH_LIMIT:
        raise StackDepthLimit("Stack depth limit reached")

    if message.value:
        sender_balance = evm.block.state_db.get_balance(message.sender)

        if sender_balance < message.value:
            raise InsufficientFunds(
                "Insufficient funds: {0} < {1}".format(sender_balance, message.value)
            )

        sender_balance -= message.value
        evm.block.state_db.set_balance(message.sender, sender_balance)

        recipient_balance = evm.block.state_db.get_balance(message.storage_address)
        recipient_balance += message.value
        evm.block.state_db.set_balance(message.storage_address, recipient_balance)

        if evm.logger is not None:
            evm.logger.debug(
                "TRANSFERRED: %s from %s -> %s",
                message.value,
                message.sender,
                message.storage_address,
            )

    computation = evm.apply_computation(message)

    if computation.error:
        evm.revert(snapshot)
    return computation


def _apply_computation(evm, message):
    computation = Computation(evm, message)

    with computation:
        # Early exit on pre-compiles
        if computation.msg.to in PRECOMPILES:
            return PRECOMPILES[computation.msg.to](computation)

        for opcode in computation.code:
            opcode_fn = computation.evm.get_opcode_fn(opcode)

            if computation.logger is not None:
                computation.logger.trace(
                    "OPCODE: 0x%x (%s)",
                    opcode_fn.value,
                    opcode_fn.mnemonic,
                )

            opcode_fn(computation=computation)

            if opcode in BREAK_OPCODES:
                break

    return computation


class BaseEVM(object):
    db = None
    block = None
    opcodes = None

    logger = logging.getLogger('evm.vm.evm.EVM')

    def __init__(self, db, block):
        self.db = db
        self.block = block

    @classmethod
    def configure(cls, name, opcodes):
        props = {
            'opcodes': {
                opcode.value: opcode
                for opcode
                in opcodes
            },
            'logger': logging.getLogger('evm.vm.evm.EVM.{0}'.format(name))
        }
        return type(name, (cls,), props)

    #
    # Execution
    #
    apply_transaction = _apply_transaction
    apply_create_message = _apply_create_message
    apply_message = _apply_message
    apply_computation = _apply_computation

    #
    # Storage
    #
    def get_block_hash(self, block_number):
        return self.db.get_block_hash(block_number)

    #
    # Snapshot and Revert
    #
    def snapshot(self):
        return self.block.state_db.snapshot()

    def revert(self, snapshot):
        return self.block.state_db.revert(snapshot)

    #
    # Opcode API
    #
    def get_opcode_fn(self, opcode):
        try:
            return self.opcodes[opcode]
        except KeyError:
            return InvalidOpcode(opcode)
