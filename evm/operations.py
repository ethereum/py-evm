from evm.utils.number import (
    UINT_256_MAX,
    integer_to_32bytes,
    big_endian_to_integer,
)


def push_XX(evm, local_state, code_stream, size):
    value_to_push = code_stream.read(size)
    if len(value_to_push) != size:
        raise ValueError("Insufficient data to read from stream")
    # eww mutation
    local_state.stack.append(value_to_push)


def add(evm, local_state, code_stream):
    left = big_endian_to_integer(local_state.stack.pop())
    right = big_endian_to_integer(local_state.stack.pop())
    local_state.stack.append(
        integer_to_32bytes((left + right) & UINT_256_MAX)
    )


def sstore(evm, local_state, code_stream):
    slot = local_state.stack.pop()
    value = local_state.stack.pop()

    evm.set_storage(local_state.account, slot, value)
