from evm import constants

from evm.utils.padding import (
    pad_left,
)


def mstore(computation):
    start_position = computation.stack.pop(type_hint=constants.UINT256)
    value = computation.stack.pop(type_hint=constants.BYTES)

    padded_value = pad_left(value, 32, b'\x00')
    normalized_value = padded_value[-32:]

    computation.extend_memory(start_position, 32)

    computation.memory.write(start_position, 32, normalized_value)


def mstore8(computation):
    start_position = computation.stack.pop(type_hint=constants.UINT256)
    value = computation.stack.pop(type_hint=constants.BYTES)

    padded_value = pad_left(value, 1, b'\x00')
    normalized_value = padded_value[-1:]

    computation.extend_memory(start_position, 1)

    computation.memory.write(start_position, 1, normalized_value)


def mload(computation):
    start_position = computation.stack.pop(type_hint=constants.UINT256)

    computation.extend_memory(start_position, 32)

    value = computation.memory.read(start_position, 32)
    computation.stack.push(value)


def msize(computation):
    computation.stack.push(len(computation.memory))
