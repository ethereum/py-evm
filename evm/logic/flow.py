from evm.constants import (
    EMPTY_WORD,
)
from evm.gas import (
    COST_SSET,
    COST_SRESET,
    REFUND_SCLEAR,
)
from evm.utils.numeric import (
    big_endian_to_int,
)


def return_op(message, storage, state):
    start_position_as_bytes = state.stack.pop()
    size_as_bytes = state.stack.pop()

    start_position = big_endian_to_int(start_position_as_bytes)
    size = big_endian_to_int(size_as_bytes)

    state.extend_memory(start_position, size)

    output = state.memory.read(start_position, size)
    state.output = output
