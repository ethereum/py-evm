from evm.constants import (
    UINT_256_MAX,
)

from evm.utils.numeric import (
    big_endian_to_int,
    integer_to_32bytes,
)


def add(storage, state, code_stream):
    left = big_endian_to_int(state.stack.pop())
    right = big_endian_to_int(state.stack.pop())
    state.stack.push(
        integer_to_32bytes((left + right) & UINT_256_MAX)
    )
