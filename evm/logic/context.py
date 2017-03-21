import logging

from eth_utils import (
    pad_right,
)

from evm import constants
from evm.exceptions import (
    OutOfGas,
)

from evm.utils.numeric import (
    ceil32,
    big_endian_to_int,
    int_to_big_endian,
)


logger = logging.getLogger('evm.logic.context')


def caller(environment):
    logger.info('CALLER: %s', environment.message.sender)
    environment.state.stack.push(environment.message.sender)


def callvalue(environment):
    logger.info('CALLVALUE: %s', environment.message.value)
    environment.state.stack.push(int_to_big_endian(environment.message.value))


def calldataload(environment):
    """
    Load call data into memory.
    """
    start_position = big_endian_to_int(environment.state.stack.pop())

    value = environment.message.data[start_position:start_position + 32]
    padded_value = pad_right(value, 32, b'\x00')
    normalized_value = padded_value.lstrip(b'\x00')

    logger.info(
        'CALLDATALOAD: [%s:%s] -> %s',
        start_position,
        start_position + 32,
        normalized_value,
    )
    environment.state.stack.push(normalized_value)


def codecopy(environment):
    current_pc = environment.state.code.pc

    mem_start_position = big_endian_to_int(environment.state.stack.pop())
    code_start_position = big_endian_to_int(environment.state.stack.pop())
    size = big_endian_to_int(environment.state.stack.pop())

    environment.state.extend_memory(mem_start_position, size)

    word_count = ceil32(size) // 32
    copy_gas_cost = constants.GAS_COPY * word_count

    environment.state.gas_meter.consume_gas(copy_gas_cost)
    if environment.state.gas_meter.is_out_of_gas:
        raise OutOfGas("Insufficient gas to copy data")

    environment.state.code.pc = code_start_position

    code_bytes = environment.state.code.read(size)
    padded_code_bytes = pad_right(code_bytes, size, b'\x00')

    environment.state.memory.write(mem_start_position, size, code_bytes)

    environment.state.code.pc = current_pc

    logger.info(
        "CODECOPY: [%s, %s] -> %s",
        code_start_position,
        code_start_position + size,
        code_bytes
    )


def data_copy(compustate, size):
    if size:
        copyfee = opcodes.GCOPY * utils.ceil32(size) // 32
        if compustate.gas < copyfee:
            compustate.gas = 0
            return False
        compustate.gas -= copyfee
    return True
