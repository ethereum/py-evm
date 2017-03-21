import logging

from eth_utils import (
    pad_right,
)

from evm import constants
from evm.exceptions import (
    OutOfGas,
    InsufficientFunds,
)

from evm.utils.address import (
    force_bytes_to_address,
)
from evm.utils.numeric import (
    big_endian_to_int,
    int_to_big_endian,
)


logger = logging.getLogger('evm.logic.system')


def return_op(environment):
    start_position_as_bytes = environment.state.stack.pop()
    size_as_bytes = environment.state.stack.pop()

    start_position = big_endian_to_int(start_position_as_bytes)
    size = big_endian_to_int(size_as_bytes)

    environment.state.extend_memory(start_position, size)

    output = environment.state.memory.read(start_position, size)
    environment.state.output = output

    logger.info('RETURN: (%s:%s) -> %s', start_position, start_position + size, output)


def suicide(environment):
    beneficiary = force_bytes_to_address(environment.state.stack.pop())
    environment.register_account_for_deletion(beneficiary)
    logger.info('SUICIDE: %s -> %s', environment.message.account, beneficiary)



def call_extra_gas_cost(to, value):
    transfer_gas_cost = constants.GAS_CALLVALUE if value else 0
    create_gas_cost = constants.GAS_CREATE if to == constants.ZERO_ADDRESS else 0

    extra_gas = transfer_gas_cost + create_gas_cost

    return extra_gas


def call(environment):
    gas = big_endian_to_int(environment.state.stack.pop())
    to = force_bytes_to_address(environment.state.stack.pop())
    value = big_endian_to_int(environment.state.stack.pop())

    memory_input_start_position = big_endian_to_int(environment.state.stack.pop())
    memory_input_size = big_endian_to_int(environment.state.stack.pop())

    memory_output_start_position = big_endian_to_int(environment.state.stack.pop())
    memory_output_size = big_endian_to_int(environment.state.stack.pop())

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

    environment.state.extend_memory(memory_input_start_position, memory_input_size)
    environment.state.extend_memory(memory_output_start_position, memory_output_size)

    call_data = environment.state.memory.read(memory_input_start_position, memory_input_size)

    extra_gas = call_extra_gas_cost(to=to, value=value)
    sub_message_gas = gas + (constants.GAS_CALLSTIPEND if value else 0)

    if environment.state.gas_meter.gas_remaining < gas + extra_gas:
        raise OutOfGas("Ran out of gas making CALL")

    sub_message = environment.create_message(
        gas=sub_message_gas,
        to=to,
        value=value,
        data=call_data,
    )
    sub_environment = environment.apply_message(sub_message)

    insufficient_funds = environment.storage.get_balance(environment.message.account) < value
    stack_too_deep = environment.message.depth >= 1024

    if insufficient_funds or stack_too_deep:
        environment.state.gas_meter.consume_gas(gas + extra_gas - sub_message_gas)
        environment.state.stack.push(int_to_big_endian(0))
    else:
        environment.state.gas_meter.consume_gas(gas + extra_gas - sub_message_gas)
        if not sub_environment.error:
            environment.state.gas_meter.return_gas(sub_environment.state.gas_meter.gas_remaining)
        padded_return_data = pad_right(sub_environment.output, memory_output_size, b'\x00')
        environment.state.memory.write(
            memory_output_start_position,
            memory_output_size,
            padded_return_data,
        )
        environment.state.stack.push(int_to_big_endian(1))
