from evm.constants import (
    UINT_256_MAX,
)
from evm.gas import (
    COST_VERYLOW,
)

from evm.utils.numeric import (
    big_endian_to_int,
    integer_to_32bytes,
)


def add(message, storage, state):
    left = big_endian_to_int(state.stack.pop())
    right = big_endian_to_int(state.stack.pop())
    state.stack.push(
        integer_to_32bytes((left + right) & UINT_256_MAX)
    )
    state.consume_gas(COST_VERYLOW)
