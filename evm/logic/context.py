from evm import constants
from evm.exceptions import (
    OutOfBoundsRead,
)

from evm.utils.address import (
    force_bytes_to_address,
)
from evm.utils.numeric import (
    ceil32,
)


def balance(computation):
    addr = force_bytes_to_address(computation.stack.pop(type_hint=constants.BYTES))
    with computation.state_db(read_only=True) as state_db:
        balance = state_db.get_balance(addr)
    computation.stack.push(balance)


def origin(computation):
    computation.stack.push(computation.transaction_context.origin)


def address(computation):
    computation.stack.push(computation.msg.storage_address)


def caller(computation):
    computation.stack.push(computation.msg.sender)


def callvalue(computation):
    computation.stack.push(computation.msg.value)


def calldataload(computation):
    """
    Load call data into memory.
    """
    start_position = computation.stack.pop(type_hint=constants.UINT256)

    value = computation.msg.data[start_position:start_position + 32]
    padded_value = value.ljust(32, b'\x00')
    normalized_value = padded_value.lstrip(b'\x00')

    computation.stack.push(normalized_value)


def calldatasize(computation):
    size = len(computation.msg.data)
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

    computation.gas_meter.consume_gas(copy_gas_cost, reason="CALLDATACOPY fee")

    value = computation.msg.data[calldata_start_position: calldata_start_position + size]
    padded_value = value.ljust(size, b'\x00')

    computation.memory.write(mem_start_position, size, padded_value)


def codesize(computation):
    size = len(computation.code)
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

    padded_code_bytes = code_bytes.ljust(size, b'\x00')

    computation.memory.write(mem_start_position, size, padded_code_bytes)


def gasprice(computation):
    computation.stack.push(computation.transaction_context.gas_price)


def PAYGAS_gasprice(computation):
    computation.stack.push(computation.get_PAYGAS_gas_price())


def extcodesize(computation):
    account = force_bytes_to_address(computation.stack.pop(type_hint=constants.BYTES))
    with computation.state_db(read_only=True) as state_db:
        code_size = len(state_db.get_code(account))

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

    with computation.state_db(read_only=True) as state_db:
        code = state_db.get_code(account)

    code_bytes = code[code_start_position:code_start_position + size]
    padded_code_bytes = code_bytes.ljust(size, b'\x00')

    computation.memory.write(mem_start_position, size, padded_code_bytes)


def returndatasize(computation):
    size = len(computation.return_data)
    computation.stack.push(size)


def returndatacopy(computation):
    (
        mem_start_position,
        returndata_start_position,
        size,
    ) = computation.stack.pop(num_items=3, type_hint=constants.UINT256)

    if returndata_start_position + size > len(computation.return_data):
        raise OutOfBoundsRead(
            "Return data length is not sufficient to satisfy request.  Asked "
            "for data from index {0} to {1}.  Return data is {2} bytes in "
            "length.".format(
                returndata_start_position,
                returndata_start_position + size,
                len(computation.return_data),
            )
        )

    computation.extend_memory(mem_start_position, size)

    word_count = ceil32(size) // 32
    copy_gas_cost = word_count * constants.GAS_COPY

    computation.gas_meter.consume_gas(copy_gas_cost, reason="RETURNDATACOPY fee")

    value = computation.return_data[returndata_start_position: returndata_start_position + size]

    computation.memory.write(mem_start_position, size, value)


def sighash(computation):
    computation.stack.push(computation.transaction_context.sig_hash)
