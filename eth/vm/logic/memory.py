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


# EIP-5656
def mcopy(computation: ComputationAPI) -> None:
    # terminology directly from the eip
    dst = computation.stack_pop1_int()
    src = computation.stack_pop1_int()
    length = computation.stack_pop1_int()

    computation.extend_memory(max(dst, src), length)

    computation.memory_copy(dst, src, length)
