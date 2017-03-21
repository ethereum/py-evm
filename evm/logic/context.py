import logging

from eth_utils import (
    pad_right,
)

from evm import constants
from evm.exceptions import (
    OutOfGas,
)

from evm.utils.address import (
    force_bytes_to_address,
)
from evm.utils.numeric import (
    ceil32,
    big_endian_to_int,
    int_to_big_endian,
)


logger = logging.getLogger('evm.logic.context')


def address(environment):
    logger.info('CALLER: %s', environment.message.account)
    environment.state.stack.push(environment.message.account)


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
    mem_start_position = big_endian_to_int(environment.state.stack.pop())
    code_start_position = big_endian_to_int(environment.state.stack.pop())
    size = big_endian_to_int(environment.state.stack.pop())

    environment.state.extend_memory(mem_start_position, size)

    word_count = ceil32(size) // 32
    copy_gas_cost = constants.GAS_COPY * word_count

    environment.state.gas_meter.consume_gas(copy_gas_cost)
    if environment.state.gas_meter.is_out_of_gas:
        raise OutOfGas("Insufficient gas to copy data")

    with environment.state.code.seek(code_start_position):
        code_bytes = environment.state.code.read(size)

    padded_code_bytes = pad_right(code_bytes, size, b'\x00')

    environment.state.memory.write(mem_start_position, size, padded_code_bytes)

    logger.info(
        "CODECOPY: [%s, %s] -> %s",
        code_start_position,
        code_start_position + size,
        padded_code_bytes,
    )


def calldatacopy(environment):
    mem_start_position = big_endian_to_int(environment.state.stack.pop())
    calldata_start_position = big_endian_to_int(environment.state.stack.pop())
    size = big_endian_to_int(environment.state.stack.pop())

    environment.state.extend_memory(mem_start_position, size)

    value = environment.message.data[calldata_start_position: calldata_start_position + size]
    padded_value = pad_right(value, size, b'\x00')

    environment.state.memory.write(mem_start_position, size, padded_value)

    logger.info(
        "CALLDATACOPY: [%s: %s] -> %s",
        calldata_start_position,
        calldata_start_position + size,
        padded_value,
    )


def extcodesize(environment):
    account = force_bytes_to_address(environment.state.stack.pop())
    code_size = len(environment.storage.get_code(account))

    logger.info('EXTCODESIZE: %s', code_size)

    environment.state.stack.push(int_to_big_endian(code_size))


def extcodecopy(environment):
    account = force_bytes_to_address(environment.state.stack.pop())
    mem_start_position = big_endian_to_int(environment.state.stack.pop())
    code_start_position = big_endian_to_int(environment.state.stack.pop())
    size = big_endian_to_int(environment.state.stack.pop())

    environment.state.extend_memory(mem_start_position, size)

    word_count = ceil32(size) // 32
    copy_gas_cost = constants.GAS_COPY * word_count

    environment.state.gas_meter.consume_gas(copy_gas_cost)
    if environment.state.gas_meter.is_out_of_gas:
        raise OutOfGas("Insufficient gas to copy data")

    code = environment.storage.get_code(account)
    code_bytes = code[code_start_position:code_start_position + size]
    padded_code_bytes = pad_right(code_bytes, size, b'\x00')

    environment.state.memory.write(mem_start_position, size, padded_code_bytes)

    logger.info(
        'EXTCODECOPY: [%s:%s] -> %s',
        code_start_position,
        code_start_position + code_size,
        padded_code_bytes,
    )
