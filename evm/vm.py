from io import BytesIO
import itertools

from toolz import (
    partial,
)

from evm import opcodes
from evm.constants import (
    NULL_BYTE,
)
from evm.exceptions import (
    EmptyStream,
    OutOfGas,
)
from evm.validation import (
    validate_word,
    validate_canonical_address,
    validate_uint256,
    validate_is_bytes,
)
from evm.logic.lookup import OPCODE_LOOKUP

from evm.utils.numeric import (
    ceil32,
)


class Memory(object):
    memory_bytes = None

    def __init__(self):
        self.memory_bytes = bytearray()

    def extend(self, start_position, size):
        if size == 0:
            return

        new_size = ceil32(start_position + size)
        if new_size <= self.size:
            return

        size_to_extend = new_size - self.size
        self.memory_bytes.extend(itertools.repeat(0, size_to_extend))

    @property
    def size(self):
        return len(self.memory_bytes)

    @property
    def cost(self):
        size_in_words = self.size // 32
        linear_cost = size_in_words * COST_MEMORY
        quadratic_cost = size_in_words ** (2 // COST_MEMORY_QUADRATIC_DENOMINATOR)

        total_cost = linear_cost + quadratic_cost
        return total_cost


def mem_extend(mem, compustate, op, start, sz):
    if sz:
        oldsize = len(mem) // 32
        old_totalfee = oldsize * opcodes.GMEMORY + \
            oldsize ** 2 // opcodes.GQUADRATICMEMDENOM
        newsize = utils.ceil32(start + sz) // 32
        # if newsize > 524288:
        #     raise Exception("Memory above 16 MB per call not supported by this VM")
        new_totalfee = newsize * opcodes.GMEMORY + \
            newsize ** 2 // opcodes.GQUADRATICMEMDENOM
        if old_totalfee < new_totalfee:
            memfee = new_totalfee - old_totalfee
            if compustate.gas < memfee:
                compustate.gas = 0
                return False
            compustate.gas -= memfee
            m_extend = (newsize - oldsize) * 32
            mem.extend([0] * m_extend)
    return True


class Stack(object):
    _stack_values = None

    def __init__(self):
        self._stack_values = []

    def push(self, item):
        validate_word(item)
        self._stack_values.append(item)

    def pop(self):
        if not self._stack_values:
            raise ValueError("Attempt to pop from empty stack")
        return self._stack_values.pop()


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

    def read(self, size):
        value = self.code.read(size)
        if len(value) != size:
            raise EmptyStream("Expected {0} bytes.  Got {1} bytes".format(size, len(value)))
        return value

    def read1(self):
        return self.read(1)

    def __len__(self):
        return len(self.code.getvalue())

    def seek(self, position):
        if position > len(self):
            raise ValueError("Out of bounds???")
        self.code.seek(position)


class State(object):
    """
    The local computation state during EVM execution.
    """
    memory = None
    stack = None
    pc = None

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

        self.logs = []

        if pc is None:
            self.pc = 0
        else:
            validate_uint256(pc)
            self.pc = pc

    @property
    def pc(self):
        return self.code.tell()

    @pc.setter
    def pc(self, value):
        self.code.seek(value)

    @property
    def gas_available(self):
        return max(self.start_gas - sum(self.gas_usage_ledger), 0)

    @property
    def total_gas_refund(self):
        return sum(self.gas_refund_ledger)

    @property
    def is_out_of_gas(self):
        return self.start_gas - sum(self.gas_usage_ledger) < 0

    def consume_gas(self, amount):
        validate_uint256(amount)
        self.gas_usage_ledger.append(amount)

    def refund_gas(self, amount):
        validate_uint256(amount)
        self.gas_refund_ledger.append(amount)

    def extend_memory(self, start_position, size):
        prev_cost = self.memory.cost
        self.memory.extend(start_position, size)

        if prev_cost < self.memory.cost:
            gas_fee = self.memory.cost - prev_cost
            sel.consume_gas(gas_fee)

        if self.is_out_of_gas:
            raise OutOfGas("Ran out of gas extending memory")


def foo():
        num_zero_bytes = str_to_bytes(self.data).count(ascii_chr(0))
        num_non_zero_bytes = len(self.data) - num_zero_bytes
        return (opcodes.GTXCOST
                + opcodes.GTXDATAZERO * num_zero_bytes
                + opcodes.GTXDATANONZERO * num_non_zero_bytes)

class Result(object):
    """
    The result of EVM computation
    """
    message = None
    state = None
    output = None

    def __init__(self, message, state, output):
        self.message = message
        self.state = state

        validate_is_bytes(output)
        self.output = output

    @property
    def gas_used(self):
        return self.state.start_gas - self.state.gas_available


def execute_vm(evm, message, state=None):
    if state is None:
        code = evm.storage.get_code(message.account)
        state = State(code, start_gas=message.gas)

    while True:
        try:
            opcode_as_bytes = state.code.read1()
        except EmptyStream:
            break

        opcode = ord(opcode_as_bytes)
        opcode_fn = OPCODE_LOOKUP[opcode]

        opcode_fn(message=message, state=state, storage=evm.storage)

        if state.is_out_of_gas:
            raise OutOfGas("Ran out of gas during execution")

    result = Result(message, state, b'')

    return evm, result


class EVM(object):
    storage = None

    def __init__(self, storage):
        self.storage = storage

    execute = execute_vm
