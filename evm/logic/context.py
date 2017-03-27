import logging


from evm import constants

from evm.utils.address import (
    force_bytes_to_address,
)
from evm.utils.numeric import (
    ceil32,
)
from evm.utils.padding import (
    pad_right,
)


logger = logging.getLogger('evm.logic.context')


def balance(computation):
    addr = force_bytes_to_address(computation.stack.pop(type_hint=constants.BYTES))
    balance = computation.storage.get_balance(addr)
    logger.info('BALANCE: %s', balance)
    computation.stack.push(balance)


def origin(computation):
    logger.info('ORIGIN: %s', computation.msg.origin)
    computation.stack.push(computation.msg.origin)


def address(computation):
    logger.info('ADDRESS: %s', computation.msg.to)
    computation.stack.push(computation.msg.to)


def caller(computation):
    logger.info('CALLER: %s', computation.msg.sender)
    computation.stack.push(computation.msg.sender)


def callvalue(computation):
    logger.info('CALLVALUE: %s', computation.msg.value)
    computation.stack.push(computation.msg.value)


def calldataload(computation):
    """
    Load call data into memory.
    """
    start_position = computation.stack.pop(type_hint=constants.UINT256)

    value = computation.msg.data[start_position:start_position + 32]
    padded_value = pad_right(value, 32, b'\x00')
    normalized_value = padded_value.lstrip(b'\x00')

    logger.info(
        'CALLDATALOAD: [%s:%s] -> %s',
        start_position,
        start_position + 32,
        normalized_value,
    )
    computation.stack.push(normalized_value)


def calldatasize(computation):
    size = len(computation.msg.data)
    logger.info('CALLDATASIZE: %s', size)
    computation.stack.push(size)


def calldatacopy(computation):
    (
        mem_start_position,
        calldata_start_position,
        size,
    ) = computation.stack.pop(num_items=3, type_hint=constants.UINT256)

    computation.extend_memory(mem_start_position, size)

    word_count = ceil32(size) // 32
    copy_gas_cost = word_count * constants.GAS_COPY

    computation.gas_meter.consume_gas(copy_gas_cost, reason="Data copy fee")

    value = computation.msg.data[calldata_start_position: calldata_start_position + size]
    padded_value = pad_right(value, size, b'\x00')

    computation.memory.write(mem_start_position, size, padded_value)

    logger.info(
        "CALLDATACOPY: [%s: %s] -> %s",
        calldata_start_position,
        calldata_start_position + size,
        padded_value,
    )


def codesize(computation):
    size = len(computation.code)
    logger.info('CODESIZE: %s', size)
    computation.stack.push(size)


def codecopy(computation):
    (
        mem_start_position,
        code_start_position,
        size,
    ) = computation.stack.pop(num_items=3, type_hint=constants.UINT256)

    computation.extend_memory(mem_start_position, size)

    word_count = ceil32(size) // 32
    copy_gas_cost = constants.GAS_COPY * word_count

    computation.gas_meter.consume_gas(
        copy_gas_cost,
        reason="CODECOPY: word gas cost",
    )

    with computation.code.seek(code_start_position):
        code_bytes = computation.code.read(size)

    padded_code_bytes = pad_right(code_bytes, size, b'\x00')

    computation.memory.write(mem_start_position, size, padded_code_bytes)

    logger.info(
        "CODECOPY: [%s, %s] -> %s",
        code_start_position,
        code_start_position + size,
        padded_code_bytes,
    )


def gasprice(computation):
    logger.info('GASPRICE: %s', computation.msg.gas_price)
    computation.stack.push(computation.msg.gas_price)


def extcodesize(computation):
    account = force_bytes_to_address(computation.stack.pop(type_hint=constants.BYTES))
    code_size = len(computation.storage.get_code(account))

    logger.info('EXTCODESIZE: %s', code_size)

    computation.stack.push(code_size)


def extcodecopy(computation):
    account = force_bytes_to_address(computation.stack.pop(type_hint=constants.BYTES))
    (
        mem_start_position,
        code_start_position,
        size,
    ) = computation.stack.pop(num_items=3, type_hint=constants.UINT256)

    computation.extend_memory(mem_start_position, size)

    word_count = ceil32(size) // 32
    copy_gas_cost = constants.GAS_COPY * word_count

    computation.gas_meter.consume_gas(
        copy_gas_cost,
        reason='EXTCODECOPY: word gas cost',
    )

    code = computation.storage.get_code(account)
    code_bytes = code[code_start_position:code_start_position + size]
    padded_code_bytes = pad_right(code_bytes, size, b'\x00')

    computation.memory.write(mem_start_position, size, padded_code_bytes)

    logger.info(
        'EXTCODECOPY: [%s:%s] -> %s',
        code_start_position,
        code_start_position + size,
        padded_code_bytes,
    )
