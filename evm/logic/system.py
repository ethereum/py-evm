from evm import constants

from evm.utils.address import (
    force_bytes_to_address,
    generate_contract_address,
)
from evm.utils.padding import (
    pad_right,
)


def return_op(computation):
    start_position, size = computation.stack.pop(num_items=2, type_hint=constants.UINT256)

    computation.extend_memory(start_position, size)

    output = computation.memory.read(start_position, size)
    computation.output = bytes(output)


def suicide(computation):
    beneficiary = force_bytes_to_address(computation.stack.pop(type_hint=constants.BYTES))
    computation.register_account_for_deletion(beneficiary)


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

    computation.extend_memory(memory_input_start_position, memory_input_size)
    computation.extend_memory(memory_output_start_position, memory_output_size)

    call_data = computation.memory.read(memory_input_start_position, memory_input_size)

    account_exists = computation.evm.block.state_db.account_exists(to)
    transfer_gas_cost = constants.GAS_CALLVALUE if value else 0
    create_gas_cost = constants.GAS_NEWACCOUNT if not account_exists else 0

    extra_gas = transfer_gas_cost + create_gas_cost

    child_msg_gas = gas + (constants.GAS_CALLSTIPEND if value else 0)

    computation.gas_meter.consume_gas(gas + extra_gas, reason="CALL")

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

    computation.extend_memory(memory_input_start_position, memory_input_size)
    computation.extend_memory(memory_output_start_position, memory_output_size)

    call_data = computation.memory.read(memory_input_start_position, memory_input_size)

    account_exists = computation.evm.block.state_db.account_exists(to)
    transfer_gas_cost = constants.GAS_CALLVALUE if value else 0
    create_gas_cost = constants.GAS_NEWACCOUNT if not account_exists else 0

    extra_gas = transfer_gas_cost + create_gas_cost

    child_msg_gas = gas + (constants.GAS_CALLSTIPEND if value else 0)

    computation.gas_meter.consume_gas(gas + extra_gas, reason="CALL")

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

    computation.extend_memory(start_position, size)

    insufficient_funds = computation.evm.block.state_db.get_balance(computation.msg.to) < value
    stack_too_deep = computation.msg.depth >= 1024

    if insufficient_funds or stack_too_deep:
        computation.stack.push(0)
        return

    call_data = computation.memory.read(start_position, size)

    create_msg_gas = computation.gas_meter.gas_remaining
    computation.gas_meter.consume_gas(create_msg_gas, reason="CREATE message gas")

    creation_nonce = computation.evm.block.state_db.get_nonce(computation.msg.to)
    contract_address = generate_contract_address(computation.msg.to, creation_nonce)

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
