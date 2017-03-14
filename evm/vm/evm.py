from io import BytesIO

from toolz import (
    partial,
)

from evm import opcodes
from evm.exceptions import (
    EmptyStream,
)
from evm.operations import (
    math as math_ops,
    storage as storage_ops,
    stack as stack_ops,
)
from evm.state import ComputationState

from .base import BaseVM


class CodeStream(object):
    code = None

    def __init__(self, code):
        self.code = BytesIO(code)

    def read(self, size):
        value = self.code.read(size)
        if len(value) != size:
            raise EmptyStream("Expected {0} bytes.  Got {1} bytes".format(size, len(value)))
        return value

    def read1(self):
        return self.read(1)


OPCODES = {
    opcodes.PUSH1: partial(stack_ops.push_XX, size=1),
    opcodes.PUSH32: partial(stack_ops.push_XX, size=32),
    opcodes.ADD: math_ops.add,
    opcodes.SSTORE: storage_ops.sstore,
}


def execute_vm(storage, gas, gas_price, origin, account, sender, value, data):
    state = ComputationState(
        gas=gas,
        gas_price=gas_price,
        origin=origin,
        account=account,
        sender=sender,
        value=value,
        data=data,
    )

    code_raw = storage.get_code(account)
    code = CodeStream(code_raw)

    while True:
        try:
            opcode_as_bytes = code.read1()
        except EmptyStream:
            break

        opcode = ord(opcode_as_bytes)
        opcode_fn = OPCODES[opcode]
        opcode_fn(storage, state, code)

    return storage
