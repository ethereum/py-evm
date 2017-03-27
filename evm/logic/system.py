import logging

from evm import constants
from evm.exceptions import (
    OutOfGas,
    InsufficientFunds,
)

from evm.utils.address import (
    force_bytes_to_address,
    generate_contract_address,
)
from evm.utils.numeric import (
    big_endian_to_int,
    int_to_big_endian,
)
from evm.utils.padding import (
    pad_right,
)


logger = logging.getLogger('evm.logic.system')


def return_op(computation):
    start_position, size = computation.stack.pop(num_items=2, type_hint=constants.UINT256)

    computation.extend_memory(start_position, size)

    output = computation.memory.read(start_position, size)
    computation.output = output

    logger.info('RETURN: (%s:%s) -> %s', start_position, start_position + size, output)


def suicide(computation):
    beneficiary = force_bytes_to_address(computation.stack.pop(type_hint=constants.BYTES))
    computation.register_account_for_deletion(beneficiary)
    logger.info('SUICIDE: %s -> %s', computation.msg.to, beneficiary)



def _call_extra_gas_cost(to, value, account_exists):
    transfer_gas_cost = constants.GAS_CALLVALUE if value else 0
    create_gas_cost = constants.GAS_NEWACCOUNT if not account_exists else 0

    extra_gas = transfer_gas_cost + create_gas_cost

    return extra_gas


def call(computation):
    gas = computation.stack.pop(type_hint=constants.UINT256)
    to = force_bytes_to_address(computation.stack.pop(type_hint=constants.BYTES))

    (
        value,
        memory_input_start_position,
        memory_input_size,
        memory_output_start_position,
        memory_output_size,
    ) = computation.stack.pop(num_items=5, type_hint=constants.UINT256)

    logger.info(
        "CALL: gas: %s | to: %s | value: %s | memory-in: [%s:%s] | memory-out: [%s:%s]",
        gas,
        to,
        value,
        memory_input_start_position,
        memory_input_start_position + memory_input_size,
        memory_output_start_position,
        memory_output_start_position + memory_output_size,
    )

    computation.extend_memory(memory_input_start_position, memory_input_size)
    computation.extend_memory(memory_output_start_position, memory_output_size)

    call_data = computation.memory.read(memory_input_start_position, memory_input_size)

    extra_gas = _call_extra_gas_cost(
        to=to,
        value=value,
        account_exists=computation.storage.account_exists(to),
    )
    child_msg_gas = gas + (constants.GAS_CALLSTIPEND if value else 0)

    computation.gas_meter.consume_gas(gas + extra_gas, reason="CALL")

    if computation.gas_meter.is_out_of_gas:
        raise OutOfGas("Insufficient gas for CALL operation")

    child_msg = computation.prepare_child_message(
        gas=child_msg_gas,
        to=to,
        value=value,
        data=call_data,
    )
    child_computation = computation.apply_child_message(child_msg)

    if child_computation.error:
        computation.gas_meter.return_gas(child_msg_gas)
        computation.stack.push(0)
    else:
        computation.gas_meter.return_gas(child_computation.gas_meter.gas_remaining)
        padded_return_data = pad_right(child_computation.output, memory_output_size, b'\x00')
        computation.memory.write(
            memory_output_start_position,
            memory_output_size,
            padded_return_data,
        )
        computation.stack.push(1)


def callcode(computation):
    gas = computation.stack.pop(type_hint=constants.UINT256)
    to = force_bytes_to_address(computation.stack.pop(type_hint=constants.BYTES))

    (
        value,
        memory_input_start_position,
        memory_input_size,
        memory_output_start_position,
        memory_output_size,
    ) = computation.stack.pop(num_items=5, type_hint=constants.UINT256)

    logger.info(
        "CALLCODE: gas: %s | to: %s | value: %s | memory-in: [%s:%s] | memory-out: [%s:%s]",
        gas,
        to,
        value,
        memory_input_start_position,
        memory_input_start_position + memory_input_size,
        memory_output_start_position,
        memory_output_start_position + memory_output_size,
    )

    computation.extend_memory(memory_input_start_position, memory_input_size)
    computation.extend_memory(memory_output_start_position, memory_output_size)

    call_data = computation.memory.read(memory_input_start_position, memory_input_size)

    extra_gas = _call_extra_gas_cost(
        to=to,
        value=value,
        account_exists=computation.storage.account_exists(to),
    )
    child_msg_gas = gas + (constants.GAS_CALLSTIPEND if value else 0)

    computation.gas_meter.consume_gas(gas + extra_gas, reason="CALL")

    if computation.gas_meter.is_out_of_gas:
        raise OutOfGas("Insufficient gas for CALL operation")

    child_msg = computation.prepare_child_message(
        gas=child_msg_gas,
        to=computation.msg.to,
        sender=computation.msg.to,
        value=value,
        data=call_data,
        code_address=to,
    )
    child_computation = computation.apply_child_message(child_msg)

    if child_computation.error:
        computation.gas_meter.return_gas(child_msg_gas)
        computation.stack.push(0)
    else:
        computation.gas_meter.return_gas(child_computation.gas_meter.gas_remaining)
        padded_return_data = pad_right(child_computation.output, memory_output_size, b'\x00')
        computation.memory.write(
            memory_output_start_position,
            memory_output_size,
            padded_return_data,
        )
        computation.stack.push(1)


def create(computation):
    value, start_position, size = computation.stack.pop(
        num_items=3,
        type_hint=constants.UINT256,
    )

    logger.info(
        "CREATE: value: %s | memory-in: [%s:%s]",
        value,
        start_position,
        start_position + size,
    )

    computation.extend_memory(start_position, size)

    insufficient_funds = computation.storage.get_balance(computation.msg.to) < value
    stack_too_deep = computation.msg.depth >= 1024

    if insufficient_funds or stack_too_deep:
        computation.stack.push(0)
        return

    call_data = computation.memory.read(start_position, size)

    create_msg_gas = computation.gas_meter.gas_remaining
    computation.gas_meter.consume_gas(create_msg_gas, reason="CREATE message gas")

    creation_nonce = computation.storage.get_nonce(computation.msg.to)
    contract_address = generate_contract_address(computation.msg.to, creation_nonce)

    logger.info('BALANCE: %s | %s | %s', computation.msg.value, value, computation.storage.get_balance(computation.msg.to))

    logger.info("%s, %s", computation.msg.to, creation_nonce)
    logger.info(
        "CREATING: %s",
        contract_address,
    )

    child_msg = computation.prepare_child_message(
        gas=create_msg_gas,
        to=constants.ZERO_ADDRESS,
        value=value,
        data=call_data,
        create_address=contract_address,
    )
    child_computation = computation.apply_child_message(child_msg)

    if child_computation.error:
        computation.stack.push(0)
    else:
        computation.gas_meter.return_gas(child_computation.gas_meter.gas_remaining)
        computation.stack.push(contract_address)
