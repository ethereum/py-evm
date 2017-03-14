from eth_utils import (
    pad_left,
)


def push_XX(storage, state, code_stream, size):
    value_to_push = code_stream.read(size)
    padded_value_to_push = pad_left(value_to_push, 32, b'\x00')
    state.stack.push(padded_value_to_push)
