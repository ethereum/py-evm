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
    VMError,
    OutOfGas,
    InsufficientFunds,
    StackDepthLimit,
)
from evm.storage import (
    Storage,
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
    snapshot = evm.snapshot()
    evm.storage.increment_nonce(transaction.sender)

    message = Message(
        gas=transaction.gas,
        gas_price=transaction.gas_price,
        to=transaction.to,
        sender=transaction.sender,
        value=transaction.value,
        data=transaction.data,
    )
    computation = evm.apply_message(message)
    if computation.error:
        evm.revert(snapshot)
    return computation


def _apply_create_message(evm, message):
    snapshot = evm.snapshot()

    computation = evm.apply_message(message)

    if message.to != message.origin:
        evm.storage.increment_nonce(computation.msg.to)

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
                computation.storage.set_code(message.to, contract_code)
        return computation


def _apply_message(evm, message):
    snapshot = evm.snapshot()

    if message.depth >= 1024:
        raise StackDepthLimit("Stack depth limit reached")
    if message.value:
        sender_balance = evm.storage.get_balance(message.sender)

        if sender_balance < message.value:
            raise InsufficientFunds(
                "Insufficient funds: {0} < {1}".format(sender_balance, message.value)
            )

        recipient_balance = evm.storage.get_balance(message.to)

        sender_balance -= message.value
        recipient_balance += message.value

        if evm.logger is not None:
            evm.logger.info(
                "Transferred: %s from %s -> %s",
                message.value,
                message.sender,
                message.to,
            )

        evm.storage.set_balance(message.sender, sender_balance)
        evm.storage.set_balance(message.to, recipient_balance)

    computation = evm.apply_computation(message)

    if computation.error:
        evm.revert(snapshot)
    return computation


def _apply_computation(computation):
    with computation:
        if computation.logger is not None:
            computation.logger.debug(
                "EXECUTING: gas: %s | from: %s | to: %s | value: %s",
                computation.msg.gas,
                computation.msg.sender,
                computation.msg.to,
                computation.msg.value,
            )

        for opcode in computation.code:
            opcode_fn = computation.evm.get_opcode_fn(opcode)

            if computation.logger is not None:
                computation.logger.debug(
                    "OPCODE: 0x%x (%s)",
                    opcode_fn.value,
                    opcode_fn.mnemonic,
                )

            try:
                opcode_fn(computation=computation)
            except VMError as err:
                computation.error = err
                computation.gas_meter.consume_gas(
                    computation.gas_meter.gas_remaining,
                    reason=" ".join((
                        "Zeroing gas due to VM Exception:",
                        str(err),
                    )),
                )
                break

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

    @property
    def storage(self):
        return Storage(self.db)

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
    def apply_transaction(self, transaction):
        return _apply_transaction(self, transaction)

    def apply_create_message(self, message):
        return _apply_create_message(self, message)

    def apply_message(self, message):
        """
        Executes the full evm message.
        """
        return _apply_message(self, message)

    def apply_computation(self, message):
        """
        Executes only the computation for a message.
        """
        computation = Computation(
            evm=self,
            message=message,
        )
        if message.to in PRECOMPILES:
            return PRECOMPILES[message.to](computation)
        else:
            return _apply_computation(computation)

    #
    # Storage
    #
    def get_block_hash(self, block_number):
        return self.db.get_block_hash(block_number)

    #
    # Snapshot and Revert
    #
    def snapshot(self):
        return self.db.snapshot()

    def revert(self, snapshot):
        self.db.revert(snapshot)

    #
    # Opcode API
    #
    def get_opcode_fn(self, opcode):
        try:
            return self.opcodes[opcode]
        except KeyError:
            return InvalidOpcode(opcode)
