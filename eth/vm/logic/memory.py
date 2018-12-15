from eth import constants

from eth.vm.computation import BaseComputation


def mstore(computation: BaseComputation) -> None:
    start_position = computation.stack_pop(type_hint=constants.UINT256)
    value = computation.stack_pop(type_hint=constants.BYTES)

    padded_value = value.rjust(32, b'\x00')
    normalized_value = padded_value[-32:]

    computation.extend_memory(start_position, 32)

    computation.memory_write(start_position, 32, normalized_value)


def mstore8(computation: BaseComputation) -> None:
    start_position = computation.stack_pop(type_hint=constants.UINT256)
    value = computation.stack_pop(type_hint=constants.BYTES)

    padded_value = value.rjust(1, b'\x00')
    normalized_value = padded_value[-1:]

    computation.extend_memory(start_position, 1)

    computation.memory_write(start_position, 1, normalized_value)


def mload(computation: BaseComputation) -> None:
    start_position = computation.stack_pop(type_hint=constants.UINT256)

    computation.extend_memory(start_position, 32)

    value = computation.memory_read_bytes(start_position, 32)
    computation.stack_push(value)


def msize(computation: BaseComputation) -> None:
    computation.stack_push(len(computation._memory))
