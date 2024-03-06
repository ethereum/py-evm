from eth import (
    constants,
)
from eth._utils.numeric import (
    ceil32,
)
from eth.abc import (
    ComputationAPI,
)


def mstore(computation: ComputationAPI) -> None:
    start_position = computation.stack_pop1_int()
    value = computation.stack_pop1_bytes()

    padded_value = value.rjust(32, b"\x00")
    normalized_value = padded_value[-32:]

    computation.extend_memory(start_position, 32)

    computation.memory_write(start_position, 32, normalized_value)


def mstore8(computation: ComputationAPI) -> None:
    start_position = computation.stack_pop1_int()
    value = computation.stack_pop1_bytes()

    padded_value = value.rjust(1, b"\x00")
    normalized_value = padded_value[-1:]

    computation.extend_memory(start_position, 1)

    computation.memory_write(start_position, 1, normalized_value)


def mload(computation: ComputationAPI) -> None:
    start_position = computation.stack_pop1_int()

    computation.extend_memory(start_position, 32)

    value = computation.memory_read_bytes(start_position, 32)
    computation.stack_push_bytes(value)


def msize(computation: ComputationAPI) -> None:
    computation.stack_push_int(len(computation._memory))


def mcopy(computation: ComputationAPI) -> None:
    dst, src, length = computation.stack_pop_ints(3)

    # extend the memory based on the maximum of the src and dst to ensure that
    # we have enough space to copy the memory and to account for the gas cost
    computation.extend_memory(max(src, dst), length)

    word_count = ceil32(length) // 32
    g_copy = constants.GAS_COPY * word_count
    # in addition to this g_copy, the opcode also has `gas_cost=constants.GAS_VERYLOW`
    computation.consume_gas(g_copy, reason="MCOPY fee")

    computation.memory_copy(dst, src, length)
