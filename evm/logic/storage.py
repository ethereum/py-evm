from evm import constants


def sstore(computation):
    slot = computation.stack.pop(type_hint=constants.UINT256)

    original_value = computation.storage.get_storage(computation.msg.storage_address, slot)
    value = computation.stack.pop(type_hint=constants.BYTES)

    if original_value.strip(b'\x00'):
        if value.strip(b'\x00'):
            gas_cost = constants.GAS_SRESET
            gas_refund = constants.REFUND_SCLEAR
        else:
            gas_cost = constants.GAS_SRESET
            gas_refund = 0
    else:
        if value.strip(b'\x00'):
            gas_cost = constants.GAS_SSET
        else:
            gas_cost = constants.GAS_SRESET
        gas_refund = 0

    computation.gas_meter.consume_gas(gas_cost, reason="SSTORE:{0}".format(slot))
    computation.gas_meter.refund_gas(gas_refund)

    computation.storage.set_storage(computation.msg.storage_address, slot, value)


def sload(computation):
    slot = computation.stack.pop(type_hint=constants.UINT256)

    value = computation.storage.get_storage(computation.msg.storage_address, slot)
    computation.stack.push(value)
