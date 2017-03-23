import contextlib
import functools
import io
import itertools
import logging

from toolz import (
    partial,
)

from eth_utils import (
    to_normalized_address,
)

from evm import opcodes
from evm.defaults.gas_costs import (
    memory_gas_cost,
    sstore_gas_cost,
    call_gas_cost,
    OPCODE_GAS_COSTS,
)
from evm.precompile import (
    PRECOMPILES,
)
from evm.defaults.opcodes import (
    OPCODE_LOGIC_FUNCTIONS,
)
from evm.logic.invalid import (
    invalid_op,
)
from evm.constants import (
    NULL_BYTE,
)
from evm.exceptions import (
    ValidationError,
    VMError,
    OutOfGas,
    InsufficientStack,
    FullStack,
    StackDepthLimit,
)
from evm.validation import (
    validate_canonical_address,
    validate_is_bytes,
    validate_length,
    validate_lte,
    validate_gte,
    validate_uint256,
    validate_word,
    validate_opcode,
    validate_integer,
    validate_boolean,
)

from evm.utils.address import (
    generate_contract_address,
)
from evm.utils.numeric import (
    ceil32,
    int_to_big_endian,
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
        return self.bytes[start_position:start_position + size]


class Stack(object):
    """
    EVM Stack
    """
    values = None
    logger = logging.getLogger('evm.vm.Stack')

    def __init__(self):
        self.values = []

    def __len__(self):
        return len(self.values)

    def push(self, value):
        """
        Push an item onto the stack.
        """
        if len(self.values) + 1 > 1024:
            raise FullStack('Stack limit reached')

        validate_is_bytes(value)
        validate_lte(len(value), maximum=32)

        self.values.append(value)

    def pop(self):
        """
        Pop an item off thes stack.
        """
        if not self.values:
            raise InsufficientStack('Popping from empty stack')

        value = self.values.pop()

        return value

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

    logger = logging.getLogger('evm.vm.CodeStream')

    def __init__(self, code_bytes):
        validate_is_bytes(code_bytes)
        self.stream = io.BytesIO(code_bytes)

    def read(self, size):
        value = self.stream.read(size)
        return value

    def __len__(self):
        return len(self.stream.getvalue())

    def __iter__(self):
        return self

    def __next__(self):
        return self.next()

    def next(self):
        next_opcode_as_byte = self.read(1)

        if len(next_opcode_as_byte) == 1:
            next_opcode = ord(next_opcode_as_byte)
        else:
            next_opcode = opcodes.STOP

        return next_opcode

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

    def is_valid_opcode(self, position):
        with self.seek(max(0, position - 32)):
            prefix = self.read(min(position, 32))

        for offset, opcode in enumerate(reversed(prefix)):
            try:
                validate_opcode(opcode)
            except ValidationError:
                continue

            if opcode < opcodes.PUSH1 or opcode > opcodes.PUSH32:
                continue

            push_size = 1 + opcode - opcodes.PUSH1
            if push_size <= offset:
                continue

            opcode_position = position - 1 - offset
            if not self.is_valid_opcode(opcode_position):
                continue

            return False
        else:
            return True


class GasMeter(object):
    start_gas = None

    deductions = None
    refunds = None

    logger = logging.getLogger('evm.vm.GasMeter')

    def __init__(self, start_gas):
        validate_uint256(start_gas)

        self.deductions = []
        self.returns = []
        self.refunds = []
        self.start_gas = start_gas

    #
    # Write API
    #
    def consume_gas(self, amount, reason):
        try:
            validate_uint256(amount)
        except ValidationError:
            raise OutOfGas("Gas amount exceeds 256 integer size: {0} reason: {1}".format(amount, reason))

        if amount > self.gas_remaining:
            raise OutOfGas("Out of gas: Needed {0} - Remaining {1} - Reason: {2}".format(
                amount,
                self.gas_remaining,
                reason,
            ))

        before_value = self.gas_remaining
        self.deductions.append(amount)

        self.logger.debug(
            'GAS CONSUMPTION: %s - %s -> %s (%s)',
            before_value,
            amount,
            self.gas_remaining,
            reason,
        )

    def return_gas(self, amount):
        validate_uint256(amount)

        before_value = self.gas_remaining
        self.returns.append(amount)

        self.logger.info(
            'GAS RETURNED: %s + %s -> %s',
            before_value,
            amount,
            self.gas_remaining,
        )

    def refund_gas(self, amount):
        validate_uint256(amount)

        before_value = self.gas_refunded
        self.refunds.append(amount)

        self.logger.info(
            'GAS REFUND: %s + %s -> %s',
            before_value,
            amount,
            self.gas_refunded,
        )


    #
    # Read API
    #
    @property
    def gas_used(self):
        return sum(self.deductions)

    @property
    def gas_refunded(self):
        return sum(self.refunds)

    @property
    def gas_returned(self):
        return sum(self.returns)

    @property
    def gas_remaining(self):
        return self.start_gas - self.gas_used + self.gas_returned

    @property
    def is_out_of_gas(self):
        return self.gas_remaining < 0

    def wrap_opcode_fn(self, opcode, opcode_fn, gas_cost):
        opcode_mnemonic = opcodes.MNEMONICS[opcode]

        @functools.wraps(opcode_fn)
        def inner(*args, **kwargs):
            self.consume_gas(gas_cost, reason="Opcode {0}".format(opcodes.get_mnemonic(opcode)))
            return opcode_fn(*args, **kwargs)
        return inner


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

        validate_integer(depth)
        validate_gte(depth, minimum=0)
        self.depth = depth

        if code_address is not None:
            validate_canonical_address(code_address)
        self.code_address = code_address

        if create_address is not None:
            validate_canonical_address(create_address)
        self.create_address = create_address

    @property
    def is_create(self):
        return self.create_address is not None

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
        if self.is_create:
            return self.create_address
        else:
            return self.to

    @storage_address.setter
    def storage_address(self, value):
        self._storage_address = storage_address


class Environment(object):
    coinbase = None
    difficulty = None
    block_number = None
    gas_limit = None
    timestamp = None

    logger = logging.getLogger('evm.vm.Environment')

    def __init__(self, coinbase, difficulty, block_number, gas_limit, timestamp):
        validate_uint256(difficulty)
        self.difficulty = difficulty

        validate_canonical_address(coinbase)
        self.coinbase = coinbase

        validate_uint256(block_number)
        self.block_number = block_number

        validate_uint256(gas_limit)
        self.gas_limit = gas_limit

        validate_uint256(timestamp)
        self.timestamp = timestamp


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

    logger = logging.getLogger('evm.vm.Computation')

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

        before_cost = memory_gas_cost(before_size)
        after_cost = memory_gas_cost(after_size)

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
                    reason="Expanding memory {0} -> {1}".format(before_size, after_size)
                )

            if self.gas_meter.is_out_of_gas:
                raise OutOfGas("Ran out of gas extending memory")

            self.memory.extend(start_position, size)

    #
    # Opcode Functions
    #
    def get_opcode_fn(self, opcode):
        try:
            validate_opcode(opcode)
        except ValidationError:
            opcode_fn = partial(invalid_op, opcode=opcode)
        else:
            base_opcode_fn = self.evm.get_base_opcode_fn(opcode)
            opcode_gas_cost = self.evm.get_opcode_gas_cost(opcode)
            opcode_fn = self.gas_meter.wrap_opcode_fn(
                opcode=opcode,
                opcode_fn=base_opcode_fn,
                gas_cost=opcode_gas_cost,
            )

        return opcode_fn

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
                self.logger.info('DELETING ACCOUNT: %s', to_normalized_address(account))
                self.storage.delete_storage(account)
                self.storage.delete_code(account)

                account_balance = self.storage.get_balance(account)
                self.storage.set_balance(account, 0)

                beneficiary_balance = self.storage.get_balance(beneficiary)
                beneficiary_updated_balance = beneficiary_balance + account_balance
                self.storage.set_balance(beneficiary, beneficiary_updated_balance)


BREAK_OPCODES = {
    opcodes.RETURN,
    opcodes.STOP,
    opcodes.SUICIDE,
}


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

        logger.info(
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
        logger = computation.logger
        logger.debug(
            "EXECUTING: gas: %s | from: %s | to: %s | value: %s",
            computation.msg.gas,
            computation.msg.sender,
            computation.msg.to,
            computation.msg.value,
        )

        for opcode in computation.code:
            opcode_mnemonic = opcodes.get_mnemonic(opcode)
            logger.debug("OPCODE: 0x%x (%s)", opcode, opcode_mnemonic)

            opcode_fn = computation.get_opcode_fn(opcode)

            try:
                opcode_fn(computation=computation)
            except VMError as err:
                computation.error = err
                computation.gas_meter.consume_gas(
                    computation.gas_meter.gas_remaining,
                    reason="Zeroing gas due to VM Exception: {0}".format(str(err)),
                )
                break

            if opcode in BREAK_OPCODES:
                break

    return computation


class EVM(object):
    storage = None
    environment = None

    def __init__(self, storage, environment):
        self.storage = storage
        self.environment = environment

    #
    # Execution
    #
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
    # Snapshot and Revert
    #
    def snapshot(self):
        return self.storage.snapshot()

    def revert(self, snapshot):
        self.storage.revert(snapshot)

    #
    # Opcode API
    #
    def get_base_opcode_fn(self, opcode):
        base_opcode_fn = OPCODE_LOGIC_FUNCTIONS[opcode]
        return base_opcode_fn

    def get_opcode_gas_cost(self, opcode):
        opcode_gas_cost = OPCODE_GAS_COSTS[opcode]
        return opcode_gas_cost

    def get_sstore_gas_fn(self):
        return sstore_gas_cost

    def get_call_gas_fn(self):
        return call_gas_cost
