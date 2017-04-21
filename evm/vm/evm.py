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
    InsufficientFunds,
    StackDepthLimit,
    ValidationError,
    InvalidTransaction,
)
from evm.validation import (
    validate_evm_block_ranges,
)

from evm.utils.address import (
    generate_contract_address,
)
from evm.utils.hexidecimal import (
    encode_hex,
)
from evm.utils.ranges import (
    range_sort_fn,
    find_range,
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
    try:
        transaction.validate()
    except ValidationError as err:
        raise InvalidTransaction(str(err))

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
        data = b''
        code = transaction.data
    else:
        contract_address = None
        data = transaction.data
        code = evm.block.state_db.get_code(transaction.to)

    if evm.logger:
        evm.logger.info(
            (
                "TRANSACTION: sender: %s | to: %s | value: %s | gas: %s | "
                "gas-price: %s | s: %s | r: %s | v: %s | data: %s"
            ),
            encode_hex(transaction.sender),
            encode_hex(transaction.to),
            transaction.value,
            transaction.gas,
            transaction.gas_price,
            transaction.s,
            transaction.r,
            transaction.v,
            encode_hex(transaction.data),
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
        evm.block.state_db.set_balance(
            evm.block.header.coinbase,
            coinbase_balance + transaction_fee,
        )
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

        if gas_refund_amount:
            if evm.logger:
                evm.logger.debug(
                    'TRANSACTION REFUND: %s -> %s',
                    gas_refund_amount,
                    encode_hex(message.sender),
                )

            sender_balance = evm.block.state_db.get_balance(message.sender)
            evm.block.state_db.set_balance(message.sender, sender_balance + gas_refund_amount)

        # Miner Fees
        transaction_fee = (transaction.gas - gas_remaining - gas_refund) * transaction.gas_price
        if evm.logger:
            evm.logger.debug(
                'TRANSACTION FEE: %s -> %s',
                transaction_fee,
                encode_hex(evm.block.header.coinbase),
            )
        coinbase_balance = evm.block.state_db.get_balance(evm.block.header.coinbase)
        evm.block.state_db.set_balance(
            evm.block.header.coinbase,
            coinbase_balance + transaction_fee,
        )

    # Suicides
    for account, beneficiary in computation.get_accounts_for_deletion():
        # TODO: need to figure out how we prevent multiple suicides from
        # the same account and if this is the right place to put this.
        if evm.logger is not None:
            evm.logger.debug('DELETING ACCOUNT: %s', encode_hex(account))

        evm.block.state_db.set_balance(account, 0)
        evm.block.state_db.delete_account(account)

    return computation


def _apply_message(evm, message):
    snapshot = evm.snapshot()

    if message.depth > constants.STACK_DEPTH_LIMIT:
        raise StackDepthLimit("Stack depth limit reached")

    if message.should_transfer_value and message.value:
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
                encode_hex(message.sender),
                encode_hex(message.storage_address),
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
                    opcode,
                    opcode_fn.mnemonic,
                )

            opcode_fn(computation=computation)

            if opcode in BREAK_OPCODES:
                break

    return computation


class BaseEVM(object):
    """
    The EVM class is... TODO:
    """
    db = None

    block = None

    opcodes = None
    block_class = None

    def __init__(self, db, header):
        self.db = db
        self.header = header

        block_class = self.get_block_class()
        self.block = block_class(header=self.header, db=self.db)

    @classmethod
    def configure(cls,
                  name,
                  **overrides):
        for key in overrides:
            if not hasattr(cls, key):
                raise TypeError(
                    "The EVM.configure cannot set attributes that are not "
                    "already present on the base class.  The attribute `{0}` was "
                    "not found on the base class `{1}`".format(key, cls)
                )
        return type(name, (cls,), overrides)

    #
    # Logging
    #
    @property
    def logger(self):
        return logging.getLogger('evm.vm.evm.EVM.{0}'.format(self.__class__.__name__))

    #
    # Execution
    #
    apply_transaction = _apply_transaction

    def apply_create_message(self, message):
        raise NotImplementedError("Must be implemented by subclasses")

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
        """
        Perform a full snapshot of the current state of the EVM.

        TODO: This needs to do more than just snapshot the state_db but this is a start.
        """
        return self.block.state_db.snapshot()

    def revert(self, snapshot):
        """
        Revert the EVM to the state

        TODO: This needs to do more than just snapshot the state_db but this is a start.
        """
        return self.block.state_db.revert(snapshot)

    #
    # Opcode API
    #
    def get_opcode_fn(self, opcode):
        try:
            return self.opcodes[opcode]
        except KeyError:
            return InvalidOpcode(opcode)


class MetaEVM(object):
    db = None
    ranges = None
    evms = None

    """
    TOOD: better name...
    The EVMChain combines multiple EVM classes into a single EVM.  Each sub-EVM

    Acknowledgement that this is not really a class but a function disguised as
    a class.  It is however easier to reason about in this format.
    """
    def __init__(self, db):
        self.db = db

    @classmethod
    def configure(cls, name, evm_block_ranges):
        if not evm_block_ranges:
            raise TypeError("MetaEVM requires at least one set of EVM rules")

        if len(evm_block_ranges) == 1:
            # edge case for a single range.
            ranges = [evm_block_ranges[0][0]]
            evms = [evm_block_ranges[0][1]]
        else:
            raw_ranges, evms = zip(*evm_block_ranges)
            ranges = tuple(sorted(raw_ranges, key=range_sort_fn))

        validate_evm_block_ranges(ranges)

        evms = {
            range: evm
            for range, evm
            in evm_block_ranges
        }

        props = {
            'ranges': ranges,
            'evms': evms,
        }
        return type(name, (cls,), props)

    def __call__(self, header):
        """
        Returns the appropriate EVM for the block
        """
        evm_class = self.get_evm_class_for_block_number(header.block_number)
        evm = evm_class(header=header, db=self.db)
        return evm

    @classmethod
    def get_evm_class_for_block_number(self, block_number):
        range = find_range(self.ranges, block_number)
        evm_class = self.evms[range]
        return evm_class
