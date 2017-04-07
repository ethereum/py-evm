from evm import constants

from evm.utils.padding import (
    pad32,
)


def sstore(computation):
    slot, value = computation.stack.pop(num_items=2, type_hint=constants.BYTES)
    padded_slot = pad32(slot)

    current_value = computation.evm.block.state_db.get_storage(
        address=computation.msg.storage_address,
        slot=padded_slot,
    )

    if current_value.strip(b'\x00'):
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

    computation.gas_meter.consume_gas(gas_cost, reason="SSTORE:{0} -> {1}".format(slot, value))
    computation.gas_meter.refund_gas(gas_refund)

    computation.evm.block.state_db.set_storage(
        address=computation.msg.storage_address,
        slot=padded_slot,
        value=value,
    )


def sload(computation):
    slot = computation.stack.pop(type_hint=constants.BYTES)
    padded_slot = pad32(slot)

    value = computation.evm.block.state_db.get_storage(
        address=computation.msg.storage_address,
        slot=padded_slot,
    )
    computation.stack.push(value)
