import logging

from toolz import (
    merge,
)

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

from evm.utils.address import (
    generate_contract_address,
)
from evm.utils.empty import (
    empty,
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
    #
    # 1) Pre Computation
    #

    # Validate the transaction
    evm.validate_transaction(transaction)

    gas_cost = transaction.gas * transaction.gas_price
    sender_balance = evm.block.state_db.get_balance(transaction.sender)

    # Buy Gas
    evm.block.state_db.set_balance(transaction.sender, sender_balance - gas_cost)

    # Increment Nonce
    evm.block.state_db.increment_nonce(transaction.sender)

    # Setup VM Message
    message_gas = transaction.gas - transaction.intrensic_gas

    if transaction.to == constants.CREATE_CONTRACT_ADDRESS:
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

    #
    # 2) Apply the message to the EVM.
    #
    if message.is_create:
        computation = evm.apply_create_message(message)
    else:
        computation = evm.apply_message(message)

    #
    # 2) Post Computation
    #
    if computation.error:
        # Miner Fees
        transaction_fee = transaction.gas * transaction.gas_price
        if evm.logger:
            evm.logger.debug('TRANSACTION FEE: %s', transaction_fee)
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
    if evm.block.state_db.account_exists(message.storage_address):
        evm.block.state_db.set_nonce(message.storage_address, 0)
        evm.block.state_db.set_code(message.storage_address, b'')
        evm.block.state_db.delete_storage(message.storage_address)

    if message.sender != message.origin:
        evm.block.state_db.increment_nonce(message.sender)

    computation = evm.apply_message(message)

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
                computation.output = b''
            else:
                if evm.logger:
                    evm.logger.debug(
                        "SETTING CODE: %s -> %s",
                        message.storage_address,
                        contract_code,
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

    if not evm.block.state_db.account_exists(message.storage_address):
        evm.block.state_db.touch_account(message.storage_address)

    computation = evm.apply_computation(message)

    if computation.error:
        evm.revert(snapshot)
    return computation


def _apply_computation(evm, message):
    computation = Computation(evm, message)

    with computation:
        # Early exit on pre-compiles
        if computation.msg.code_address in PRECOMPILES:
            return PRECOMPILES[computation.msg.code_address](computation)

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
    block_class = None

    logger = logging.getLogger('evm.vm.evm.EVM')

    def __init__(self, db, block):
        self.db = db
        self.block = block

    @classmethod
    def configure(cls,
                  name,
                  opcodes,
                  transaction_class=None,
                  block_class=None,
                  db=None,
                  logger=empty,
                  **extra_props):
        if logger is empty:
            logger = logging.getLogger('evm.vm.evm.EVM.{0}'.format(name))

        configure_props = {
            'opcodes': opcodes,
            'logger': logger,
            'transaction_class': transaction_class or cls.transaction_class,
            'block_class': block_class or cls.block_class,
            'db': db or cls.db,
        }
        for key in extra_props:
            if not hasattr(cls, key):
                raise TypeError(
                    "The EVM.configure cannot set attributes that are not "
                    "already present on the base class.  The attribute `{0}` was "
                    "not found on the base class `{1}`".format(key, cls)
                )
        props = merge(configure_props, extra_props)
        return type(name, (cls,), props)

    #
    # Execution
    #
    apply_transaction = _apply_transaction
    apply_create_message = _apply_create_message
    apply_message = _apply_message
    apply_computation = _apply_computation

    #
    # Transactions
    #
    transaction_class = None

    @classmethod
    def get_transaction_class(cls):
        """
        Return the class that this EVM uses for transactions.
        """
        if cls.transaction_class is None:
            raise AttributeError("No `transaction_class` has been set for this EVM")

        return cls.transaction_class

    def validate_transaction(self):
        raise NotImplementedError("Must be implemented by subclasses")

    #
    # Blocks
    #
    block_class = None

    @classmethod
    def get_block_class(cls):
        """
        Return the class that this EVM uses for blocks.
        """
        if cls.block_class is None:
            raise AttributeError("No `block_class` has been set for this EVM")

        return cls.block_class

    @classmethod
    def initialize_block(cls, header):
        """
        Return the class that this EVM uses for transactions.
        """
        block_class = cls.get_block_class()
        return block_class(
            header=header,
            db=cls.db,
        )

    @classmethod
    def get_block_hash(cls, block_number):
        """
        Return the block has for the requested block number.
        """
        return cls.db.get_block_hash(block_number)

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
