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
    generate_contract_address,
)
from evm.utils.numeric import (
    big_endian_to_int,
    int_to_big_endian,
)


logger = logging.getLogger('evm.logic.system')


def return_op(computation):
    start_position_as_bytes = computation.stack.pop()
    size_as_bytes = computation.stack.pop()

    start_position = big_endian_to_int(start_position_as_bytes)
    size = big_endian_to_int(size_as_bytes)

    computation.extend_memory(start_position, size)

    output = computation.memory.read(start_position, size)
    computation.output = output

    logger.info('RETURN: (%s:%s) -> %s', start_position, start_position + size, output)


def suicide(computation):
    beneficiary = force_bytes_to_address(computation.stack.pop())
    computation.register_account_for_deletion(beneficiary)
    logger.info('SUICIDE: %s -> %s', computation.msg.to, beneficiary)



def call_extra_gas_cost(to, value, account_exists):
    transfer_gas_cost = constants.GAS_CALLVALUE if value else 0
    create_gas_cost = constants.GAS_NEWACCOUNT if not account_exists else 0

    extra_gas = transfer_gas_cost + create_gas_cost

    return extra_gas


def call(computation):
    gas = big_endian_to_int(computation.stack.pop())
    to = force_bytes_to_address(computation.stack.pop())
    value = big_endian_to_int(computation.stack.pop())

    memory_input_start_position = big_endian_to_int(computation.stack.pop())
    memory_input_size = big_endian_to_int(computation.stack.pop())

    memory_output_start_position = big_endian_to_int(computation.stack.pop())
    memory_output_size = big_endian_to_int(computation.stack.pop())

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

    extra_gas = call_extra_gas_cost(
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
        computation.stack.push(int_to_big_endian(0))
    else:
        computation.gas_meter.return_gas(child_computation.gas_meter.gas_remaining)
        padded_return_data = pad_right(child_computation.output, memory_output_size, b'\x00')
        computation.memory.write(
            memory_output_start_position,
            memory_output_size,
            padded_return_data,
        )
        computation.stack.push(int_to_big_endian(1))


def callcode(computation):
    gas = big_endian_to_int(computation.stack.pop())
    to = force_bytes_to_address(computation.stack.pop())
    value = big_endian_to_int(computation.stack.pop())

    memory_input_start_position = big_endian_to_int(computation.stack.pop())
    memory_input_size = big_endian_to_int(computation.stack.pop())

    memory_output_start_position = big_endian_to_int(computation.stack.pop())
    memory_output_size = big_endian_to_int(computation.stack.pop())

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

    extra_gas = call_extra_gas_cost(
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
        computation.stack.push(int_to_big_endian(0))
    else:
        computation.gas_meter.return_gas(child_computation.gas_meter.gas_remaining)
        padded_return_data = pad_right(child_computation.output, memory_output_size, b'\x00')
        computation.memory.write(
            memory_output_start_position,
            memory_output_size,
            padded_return_data,
        )
        computation.stack.push(int_to_big_endian(1))


def create(computation):
    value = big_endian_to_int(computation.stack.pop())
    start_position = big_endian_to_int(computation.stack.pop())
    size = big_endian_to_int(computation.stack.pop())

    logger.info(
        "CREATE: value: %s | memory-in: [%s:%s]",
        value,
        start_position,
        start_position + size,
    )

    computation.extend_memory(start_position, size)

    call_data = computation.memory.read(start_position, size)

    create_msg_gas = computation.gas_meter.gas_remaining
    computation.gas_meter.consume_gas(create_msg_gas, reason="CREATE message gas")

    creation_nonce = computation.storage.get_nonce(computation.msg.to)
    contract_address = generate_contract_address(computation.msg.to, creation_nonce)

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
        computation.stack.push(int_to_big_endian(0))
    else:
        computation.gas_meter.return_gas(child_computation.gas_meter.gas_remaining)
        computation.stack.push(contract_address)


"""
value, mstart, msz = stk.pop(), stk.pop(), stk.pop()
if not mem_extend(mem, compustate, op, mstart, msz):
    return vm_exception('OOG EXTENDING MEMORY')
if ext.get_balance(msg.to) >= value and msg.depth < 1024:
    cd = CallData(mem, mstart, msz)
    ingas = compustate.gas
    # EIP150(1b) CREATE only provides all but one 64th of the
    # parent gas to the child call
    if ext.post_anti_dos_hardfork:
        ingas = max_call_gas(ingas)

    create_msg = Message(msg.to, b'', value, ingas, cd, msg.depth + 1)
    o, gas, addr = ext.create(create_msg)
    if o:
        stk.append(utils.coerce_to_int(addr))
        compustate.gas -= (ingas - gas)
    else:
        stk.append(0)
        compustate.gas -= ingas
else:
    stk.append(0)


def create_contract(ext, msg):
    log_msg.debug('CONTRACT CREATION')
    #print('CREATING WITH GAS', msg.gas)
    sender = decode_hex(msg.sender) if len(msg.sender) == 40 else msg.sender
    code = msg.data.extract_all()
    if ext._block.number >= ext._block.config['METROPOLIS_FORK_BLKNUM']:
        msg.to = mk_metropolis_contract_address(msg.sender, code)
        if ext.get_code(msg.to):
            if ext.get_nonce(msg.to) >= 2 ** 40:
                ext.set_nonce(msg.to, (ext.get_nonce(msg.to) + 1) % 2 ** 160)
                msg.to = normalize_address((ext.get_nonce(msg.to) - 1) % 2 ** 160)
            else:
                ext.set_nonce(msg.to, (big_endian_to_int(msg.to) + 2) % 2 ** 160)
                msg.to = normalize_address((ext.get_nonce(msg.to) - 1) % 2 ** 160)
    else:
        if ext.tx_origin != msg.sender:
            ext._block.increment_nonce(msg.sender)
        nonce = utils.encode_int(ext._block.get_nonce(msg.sender) - 1)
        msg.to = mk_contract_address(sender, nonce)
    b = ext.get_balance(msg.to)
    if b > 0:
        ext.set_balance(msg.to, b)
        ext._block.set_nonce(msg.to, 0)
        ext._block.set_code(msg.to, b'')
        ext._block.reset_storage(msg.to)
    msg.is_create = True
    # assert not ext.get_code(msg.to)
    msg.data = vm.CallData([], 0, 0)
    snapshot = ext._block.snapshot()
    res, gas, dat = _apply_msg(ext, msg, code)
    assert utils.is_numeric(gas)

    if res:
        if not len(dat):
            return 1, gas, msg.to
        gcost = len(dat) * opcodes.GCONTRACTBYTE
        if gas >= gcost:
            gas -= gcost
        else:
            dat = []
            log_msg.debug('CONTRACT CREATION OOG', have=gas, want=gcost, block_number=ext._block.number)
            if ext._block.number >= ext._block.config['HOMESTEAD_FORK_BLKNUM']:
                ext._block.revert(snapshot)
                return 0, 0, b''
        ext._block.set_code(msg.to, b''.join(map(ascii_chr, dat)))
        return 1, gas, msg.to
    else:
        return 0, gas, b''
"""
