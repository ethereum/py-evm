import contextlib
import io
import itertools
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
    ValidationError,
    VMError,
    OutOfGas,
    InsufficientStack,
    FullStack,
    StackDepthLimit,
    InsufficientFunds,
)
from evm.storage import (
    Storage,
)
from evm.validation import (
    validate_canonical_address,
    validate_is_bytes,
    validate_is_integer,
    validate_length,
    validate_lte,
    validate_gte,
    validate_uint256,
    validate_stack_item,
    validate_word,
)

from evm.utils.numeric import (
    ceil32,
    int_to_big_endian,
    big_endian_to_int,
)


class Memory(object):
    """
    EVM Memory
    """
    bytes = None

    def __init__(self):
        self.bytes = bytearray()

    def extend(self, start_position, size):
        if size == 0:
            return

        new_size = ceil32(start_position + size)
        if new_size <= len(self):
            return

        size_to_extend = new_size - len(self)
        self.bytes.extend(itertools.repeat(0, size_to_extend))

    def __len__(self):
        return len(self.bytes)

    def write(self, start_position, size, value):
        """
        Write `value` into memory.
        """
        if size:
            validate_uint256(start_position)
            validate_uint256(size)
            validate_is_bytes(value)
            validate_length(value, length=size)
            validate_lte(start_position + size, maximum=len(self))

            self.bytes = (
                self.bytes[:start_position] +
                bytearray(value) +
                self.bytes[start_position + size:]
            )

    def read(self, start_position, size):
        """
        Read a value from memory.
        """
        return bytes(self.bytes[start_position:start_position + size])


class Stack(object):
    """
    EVM Stack
    """
    values = None
    #logger = logging.getLogger('evm.vm.Stack')
    logger = None

    def __init__(self):
        self.values = []

    def __len__(self):
        return len(self.values)

    def push(self, value):
        """
        Push an item onto the stack.
        """
        if len(self.values) > 1023:
            raise FullStack('Stack limit reached')

        validate_stack_item(value)

        self.values.append(value)

    def pop(self, num_items=1, type_hint=None):
        """
        Pop an item off thes stack.

        Note: This function is optimized for speed over readability.
        """
        try:
            if num_items == 1:
                return next(self._pop(num_items, type_hint))
            else:
                return tuple(self._pop(num_items, type_hint))
        except IndexError:
            raise InsufficientStack("No stack items")

    def _pop(self, num_items, type_hint):
        for _ in range(num_items):
            if type_hint == constants.UINT256:
                value = self.values.pop()
                if isinstance(value, int):
                    yield value
                else:
                    yield big_endian_to_int(value)
            elif type_hint == constants.BYTES:
                value = self.values.pop()
                if isinstance(value, bytes):
                    yield value
                else:
                    yield int_to_big_endian(value)
            elif type_hint == constants.ANY:
                yield self.values.pop()
            else:
                raise TypeError(
                    "Unknown type_hint: {0}.  Must be one of {1}".format(
                        type_hint,
                        ", ".join((constants.UINT256, constants.BYTES)),
                    )
                )

    def swap(self, position):
        """
        Perform a SWAP operation on the stack.
        """
        idx = -1 * position - 1
        try:
            self.values[-1], self.values[idx] = self.values[idx], self.values[-1]
        except IndexError:
            raise InsufficientStack("Insufficient stack items for SWAP{0}".format(position))

    def dup(self, position):
        """
        Perform a DUP operation on the stack.
        """
        idx = -1 * position
        try:
            self.push(self.values[idx])
        except IndexError:
            raise InsufficientStack("Insufficient stack items for DUP{0}".format(position))


class CodeStream(object):
    stream = None

    #logger = logging.getLogger('evm.vm.CodeStream')
    logger = None

    def __init__(self, code_bytes):
        validate_is_bytes(code_bytes)
        self.stream = io.BytesIO(code_bytes)
        self._validity_cache = {}

    def read(self, size):
        return self.stream.read(size)

    def __len__(self):
        return len(self.stream.getvalue())

    def __iter__(self):
        return self

    def __next__(self):
        return self.next()

    def next(self):
        next_opcode_as_byte = self.read(1)

        if next_opcode_as_byte:
            return ord(next_opcode_as_byte)
        else:
            return opcode_values.STOP

    def peek(self):
        current_pc = self.pc
        next_opcode = next(self)
        self.pc = current_pc
        return next_opcode

    @property
    def pc(self):
        return self.stream.tell()

    @pc.setter
    def pc(self, value):
        self.stream.seek(min(value, len(self)))

    @contextlib.contextmanager
    def seek(self, pc):
        anchor_pc = self.pc
        self.pc = pc
        try:
            yield self
        except:
            raise
        finally:
            self.pc = anchor_pc

    _validity_cache = None

    def is_valid_opcode(self, position):
        if position >= len(self):
            return False

        if position not in self._validity_cache:
            with self.seek(max(0, position - 32)):
                prefix = self.read(min(position, 32))

            for offset, opcode in enumerate(reversed(prefix)):
                if opcode < opcode_values.PUSH1 or opcode > opcode_values.PUSH32:
                    continue

                push_size = 1 + opcode - opcode_values.PUSH1
                if push_size <= offset:
                    continue

                opcode_position = position - 1 - offset
                if not self.is_valid_opcode(opcode_position):
                    continue

                self._validity_cache[position] = False
                break
            else:
                self._validity_cache[position] = True

        return self._validity_cache[position]


class GasMeter(object):
    start_gas = None

    gas_refunded = None
    gas_remaining = None

    #logger = logging.getLogger('evm.vm.GasMeter')
    logger = None

    def __init__(self, start_gas):
        validate_uint256(start_gas)

        self.start_gas = start_gas

        self.gas_remaining = self.start_gas
        self.gas_refunded = 0

    #
    # Write API
    #
    def consume_gas(self, amount, reason):
        if amount < 0:
            raise ValidationError("Gas consumption amount must be positive")

        if amount > self.gas_remaining:
            raise OutOfGas("Out of gas: Needed {0} - Remaining {1} - Reason: {2}".format(
                amount,
                self.gas_remaining,
                reason,
            ))

        self.gas_remaining -= amount

        if self.logger is not None:
            self.logger.debug(
                'GAS CONSUMPTION: %s - %s -> %s (%s)',
                self.gas_remaining + amount,
                amount,
                self.gas_remaining,
                reason,
            )

    def return_gas(self, amount):
        if amount < 0:
            raise ValidationError("Gas return amount must be positive")

        self.gas_remaining += amount

        if self.logger is not None:
            self.logger.info(
                'GAS RETURNED: %s + %s -> %s',
                self.gas_remaining - amount,
                amount,
                self.gas_remaining,
            )

    def refund_gas(self, amount):
        if amount < 0:
            raise ValidationError("Gas refund amount must be positive")

        self.gas_refunded += amount

        if self.logger is not None:
            self.logger.debug(
                'GAS REFUND: %s + %s -> %s',
                self.gas_refunded - amount,
                amount,
                self.gas_refunded,
            )


class Message(object):
    """
    A message for EVM computation.
    """
    origin = None
    to = None
    sender = None
    value = None
    data = None
    gas = None
    gas_price = None

    depth = None

    _code_address = None
    create_address = None

    def __init__(self,
                 gas,
                 gas_price,
                 origin,
                 to,
                 sender,
                 value,
                 data,
                 depth=0,
                 code_address=None,
                 create_address=None):
        validate_uint256(gas)
        self.gas = gas

        validate_uint256(gas_price)
        self.gas_price = gas_price

        validate_canonical_address(origin)
        self.origin = origin

        validate_canonical_address(to)
        self.to = to

        validate_canonical_address(sender)
        self.sender = sender

        validate_uint256(value)
        self.value = value

        validate_is_bytes(data)
        self.data = data

        validate_is_integer(depth)
        validate_gte(depth, minimum=0)
        self.depth = depth

        if code_address is not None:
            validate_canonical_address(code_address)
        self.code_address = code_address

        if create_address is not None:
            validate_canonical_address(create_address)
        self.storage_address = create_address

    @property
    def code_address(self):
        if self._code_address is not None:
            return self._code_address
        else:
            return self.to

    @code_address.setter
    def code_address(self, value):
        self._code_address = value

    @property
    def storage_address(self):
        if self._storage_address is not None:
            return self._storage_address
        else:
            return self.to

    @storage_address.setter
    def storage_address(self, value):
        self._storage_address = value

    @property
    def is_create(self):
        return self._storage_address is not None


class Environment(object):
    coinbase = None
    difficulty = None
    block_number = None
    gas_limit = None
    timestamp = None
    previous_hash = None

    #logger = logging.getLogger('evm.vm.Environment')
    logger = None

    def __init__(self, coinbase, difficulty, block_number, gas_limit, timestamp, previous_hash):
        self.difficulty = difficulty

        validate_canonical_address(coinbase)
        self.coinbase = coinbase

        validate_uint256(block_number)
        self.block_number = block_number

        validate_uint256(gas_limit)
        self.gas_limit = gas_limit

        validate_uint256(timestamp)
        self.timestamp = timestamp

        validate_word(previous_hash)
        self.previous_hash = previous_hash


class Computation(object):
    """
    The execution computation
    """
    evm = None
    msg = None

    memory = None
    stack = None
    gas_meter = None

    code = None

    children = None

    output = b''
    error = None

    logs = None
    accounts_to_delete = None

    #logger = logging.getLogger('evm.vm.Computation')
    logger = None

    def __init__(self, evm, message):
        self.evm = evm
        self.msg = message

        self.memory = Memory()
        self.stack = Stack()
        self.gas_meter = GasMeter(message.gas)

        self.children = []
        self.accounts_to_delete = {}
        self.logs = []

        if message.is_create:
            code = message.data
        else:
            code = self.storage.get_code(message.code_address)
        self.code = CodeStream(code)

    @property
    def storage(self):
        return self.evm.storage

    @property
    def env(self):
        return self.evm.environment

    #
    # Execution
    #
    def prepare_child_message(self,
                              gas,
                              to,
                              value,
                              data,
                              sender=None,
                              code_address=None,
                              create_address=None):
        if sender is None:
            sender = self.msg.to

        child_message = Message(
            gas=gas,
            gas_price=self.msg.gas_price,
            origin=self.msg.origin,
            to=to,
            sender=sender,
            value=value,
            data=data,
            depth=self.msg.depth + 1,
            code_address=code_address,
            create_address=create_address,
        )
        return child_message

    def apply_child_message(self, message):
        if message.is_create:
            child_computation = self.evm.apply_create_message(message)
        else:
            child_computation = self.evm.apply_message(message)

        self.children.append(child_computation)
        return child_computation

    #
    # Memory Management
    #
    def extend_memory(self, start_position, size):
        validate_uint256(start_position)
        validate_uint256(size)

        before_size = ceil32(len(self.memory))
        after_size = ceil32(start_position + size)

        from evm.preconfigured.genesis import memory_gas_cost
        # TODO: abstract
        before_cost = memory_gas_cost(before_size)
        after_cost = memory_gas_cost(after_size)

        if self.logger is not None:
            self.logger.debug(
                "MEMORY: size (%s -> %s) | cost (%s -> %s)",
                before_size,
                after_size,
                before_cost,
                after_cost,
            )

        if size:
            if before_cost < after_cost:
                gas_fee = after_cost - before_cost
                self.gas_meter.consume_gas(
                    gas_fee,
                    reason=" ".join((
                        "Expanding memory",
                        str(before_size),
                        "->",
                        str(after_size),
                    ))
                )

            self.memory.extend(start_position, size)

    #
    # Runtime Operations
    #
    def register_account_for_deletion(self, beneficiary):
        validate_canonical_address(beneficiary)

        if self.msg.to in self.accounts_to_delete:
            raise ValueError(
                "Invariant.  Should be impossible for an account to be "
                "registered for deletion multiple times"
            )
        self.accounts_to_delete[self.msg.to] = beneficiary

    def add_log_entry(self, account, topics, data):
        self.logs.append((account, topics, data))

    #
    # Context Manager API
    #
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type and issubclass(exc_type, VMError):
            self.error = exc_value
            # suppress VM exceptions
            return True
        elif exc_type is None:
            for account, beneficiary in self.accounts_to_delete.items():
                if self.logger is not None:
                    self.logger.info('DELETING ACCOUNT: %s', account)
                self.storage.delete_storage(account)
                self.storage.delete_code(account)

                account_balance = self.storage.get_balance(account)
                self.storage.set_balance(account, 0)

                beneficiary_balance = self.storage.get_balance(beneficiary)
                beneficiary_updated_balance = beneficiary_balance + account_balance
                self.storage.set_balance(beneficiary, beneficiary_updated_balance)


BREAK_OPCODES = {
    opcode_values.RETURN,
    opcode_values.STOP,
    opcode_values.SUICIDE,
}


def _apply_transaction(evm, transaction):
    assert False


def _apply_create_message(evm, message):
    snapshot = evm.snapshot()

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


class EVM(object):
    db = None
    environment = None
    opcodes = None

    #logger = logging.getLogger('evm.vm.EVM')
    logger = None

    def __init__(self, db, environment):
        self.db = db
        self.environment = environment

    @property
    def storage(self):
        return Storage(self.db)

    @classmethod
    def create(cls, name, opcode_classes):
        props = {
            'opcodes': {
                opcode_class.value: opcode_class()
                for opcode_class in opcode_classes
            },
            'logger': logging.getLogger('evm.vm.EVM.{0}'.format(name))
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
