from io import BytesIO
import itertools
import logging

from toolz import (
    partial,
)

from evm import opcodes
from evm.gas import (
    COST_MEMORY,
    COST_MEMORY_QUADRATIC_DENOMINATOR,
)
from evm.constants import (
    NULL_BYTE,
)
from evm.exceptions import (
    VMError,
    EmptyStream,
    OutOfGas,
    InsufficientStack,
    FullStack,
)
from evm.validation import (
    validate_canonical_address,
    validate_is_bytes,
    validate_length,
    validate_lte,
    validate_uint256,
    validate_word,
)
from evm.logic.lookup import OPCODE_LOOKUP

from evm.utils.numeric import (
    ceil32,
    int_to_big_endian,
)


logger = logging.getLogger('evm.vm')


class Memory(object):
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

    @property
    def cost(self):
        size_in_words = len(self) // 32
        linear_cost = size_in_words * COST_MEMORY
        quadratic_cost = size_in_words ** (2 // COST_MEMORY_QUADRATIC_DENOMINATOR)

        total_cost = linear_cost + quadratic_cost
        return total_cost

    def write(self, start_position, size, value):
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
        return self.bytes[start_position:start_position + size]


class Stack(object):
    values = None

    def __init__(self):
        self.values = []

    def __len__(self):
        return len(self.values)

    def push(self, value):
        if len(self.values) + 1 > 1024:
            raise FullStack('Stack limit reached')
        validate_is_bytes(value)
        validate_lte(len(value), maximum=32)
        logger.info('STACK:PUSHING: %s', value)
        self.values.append(value)

    def pop(self):
        if not self.values:
            raise InsufficientStack('Insufficient stack items')
        value = self.values.pop()
        logger.info('STACK:POPPING: %s', value)
        return value

    def swap(self, position):
        idx = -1 * position
        self.values[-1], self.values[idx] = self.values[idx], self.values[-1]

    def dup(self, position):
        idx = -1 * position
        self.push(self.values[idx])


class Message(object):
    """
    A message for EVM computation.
    """
    origin = None
    account = None
    sender = None
    value = None
    data = None
    gas = None
    gas_price = None

    def __init__(self, gas, gas_price, origin, account, sender, value, data):
        validate_uint256(gas)
        self.gas = gas

        validate_uint256(gas_price)
        self.gas_price = gas_price

        validate_canonical_address(origin)
        self.origin = origin

        validate_canonical_address(account)
        self.account = account

        validate_canonical_address(sender)
        self.sender = sender

        validate_uint256(value)
        self.value = value

        validate_is_bytes(data)
        self.data = data


class CodeStream(object):
    code = None

    def __init__(self, code):
        validate_is_bytes(code)
        self.code = BytesIO(code)

    def read_raw(self, size):
        value = self.code.read(size)
        return value

    def read(self, size):
        value = self.read_raw(size)
        if len(value) != size:
            raise EmptyStream("Expected {0} bytes.  Got {1} bytes".format(size, len(value)))
        return value

    def __iter__(self):
        return self

    def __next__(self):
        return self.next()

    def next(self):
        if self.code.closed:
            raise StopIteration()
        try:
            next_op = ord(self.read(1))
            if next_op == opcodes.STOP:
                self.code.close()
            return next_op
        except EmptyStream:
            self.code.close()
            return opcodes.STOP

    def __len__(self):
        return len(self.code.getvalue())

    def seek(self, position):
        if position > len(self):
            raise ValueError("Out of bounds???")
        self.code.seek(position)


class GasMeter(object):
    start_gas = None

    deductions = None
    refunds = None

    def __init__(self, start_gas):
        self.start_gas = start_gas

    #
    # Write API
    #
    def consume_gas(self, amount):
        pass

    def refund_gas(self, amount):
        pass

    #
    # Read API
    #
    @property
    def total_used(self):
        return sum(self.deductions)

    @property
    def total_refunded(self):
        return sum(self.refunds)

    @property
    def available(self):
        return self.start_gas - self.total_used

    @property
    def is_out_of_gas(self):
        return self.available < 0

    def wrap_opcode(self, opcode_logic_fn):
        # TODO:
        #@functools.wraps(opcode_logic_fn)
        #def inner(
        pass


class State(object):
    """
    The local computation state during EVM execution.
    """
    memory = None
    stack = None
    pc = None

    output = b''
    error = None

    code = None

    start_gas = None
    gas_usage_ledger = None
    gas_refund_ledger = None

    logs = None

    def __init__(self, code, start_gas, pc=None, parent=None):
        self.memory = Memory()
        self.stack = Stack()

        validate_is_bytes(code)
        self.code = CodeStream(code)

        validate_uint256(start_gas)
        self.start_gas = start_gas

        self.gas_usage_ledger = []
        self.gas_refund_ledger = []

        self.logger = logging.getLogger('evm.vm.State')

        self.logs = []

        if pc is None:
            self.pc = 0
        else:
            validate_uint256(pc)
            self.pc = pc

    @property
    def pc(self):
        return self.code.code.tell()

    @pc.setter
    def pc(self, value):
        self.code.code.seek(value)

    @property
    def gas_available(self):
        return max(self.start_gas - sum(self.gas_usage_ledger), 0)

    @property
    def gas_used(self):
        return self.start_gas - self.gas_available

    @property
    def total_gas_refund(self):
        return sum(self.gas_refund_ledger)

    @property
    def is_out_of_gas(self):
        return self.start_gas - sum(self.gas_usage_ledger) < 0

    def consume_gas(self, amount):
        validate_uint256(amount)
        before_value = self.gas_available
        self.gas_usage_ledger.append(amount)
        self.logger.info('GAS CONSUMPTION: %s - %s -> %s', before_value, amount, self.gas_available)

    def refund_gas(self, amount):
        validate_uint256(amount)
        before_value = self.total_gas_refund
        self.gas_refund_ledger.append(amount)
        self.logger.info('GAS REFUND: %s - %s -> %s', before_value, amount, self.total_gas_refund)

    def extend_memory(self, start_position, size):
        prev_cost = self.memory.cost
        self.memory.extend(start_position, size)

        if prev_cost < self.memory.cost:
            gas_fee = self.memory.cost - prev_cost
            self.consume_gas(gas_fee)

        if self.is_out_of_gas:
            raise OutOfGas("Ran out of gas extending memory")


def execute_vm(evm, message, state=None):
    if state is None:
        code = evm.storage.get_code(message.account)
        state = State(code, start_gas=message.gas)

    for opcode in state.code:
        if state.is_out_of_gas:
            raise OutOfGas("Ran out of gas during execution")

        try:
            opcode_fn = OPCODE_LOOKUP[opcode]
        except KeyError:
            # TODO: consume all the gas..
            break

        try:
            opcode_fn(message=message, state=state, storage=evm.storage)
        except VMError as err:
            state.error = err
            break

    return evm, state


class EVM(object):
    storage = None

    def __init__(self, storage):
        self.storage = storage

    execute = execute_vm
