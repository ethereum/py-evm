import logging

from evm.utils.numeric import (
    big_endian_to_int,
)


logger = logging.getLogger('evm.logic.storage')


def sstore(computation):
    slot_as_bytes = computation.stack.pop()
    slot = big_endian_to_int(slot_as_bytes)

    original_value = computation.storage.get_storage(computation.msg.storage_address, slot)
    value = computation.stack.pop()

    logger.info('SSTORE: (%s) %s -> %s', slot, original_value, value)

    computation.storage.set_storage(computation.msg.storage_address, slot, value)

    gas_fn = computation.evm.get_sstore_gas_fn()
    gas_cost, gas_refund = gas_fn(original_value, value)

    computation.gas_meter.consume_gas(gas_cost, reason="SSTORE:{0}".format(slot))
    computation.gas_meter.refund_gas(gas_refund)


def sload(computation):
    slot_as_bytes = computation.stack.pop()
    slot = big_endian_to_int(slot_as_bytes)

    value = computation.storage.get_storage(computation.msg.storage_address, slot)
    computation.stack.push(value)

    logger.info('SLOAD: (%s) -> %s', slot, value)
