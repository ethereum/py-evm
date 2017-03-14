from io import BytesIO

from evm.validation import (
    validate_word,
    validate_canonical_address,
    validate_uint256,
    validate_is_bytes,
)


class Memory(object):
    _memory_bytes = None

    def __init__(self):
        self._memory_bytes = BytesIO()


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


class ComputationState(object):
    """
    Stores the local computation state during EVM execution.
    """
    memory = None
    stack = None

    gas = None
    gas_price = None

    origin = None

    account = None

    sender = None
    value = None
    data = None

    def __init__(self, gas, gas_price, origin, account, sender, value, data):
        self.memory = Memory()
        self.stack = Stack()

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
