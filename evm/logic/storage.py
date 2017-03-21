import logging

from evm.utils.numeric import (
    big_endian_to_int,
)


logger = logging.getLogger('evm.logic.storage')


def sstore(environment):
    slot_as_bytes = environment.state.stack.pop()
    slot = big_endian_to_int(slot_as_bytes)

    original_value = environment.storage.get_storage(environment.message.account, slot)
    value = environment.state.stack.pop()

    logger.info('SSTORE: (%s) %s -> %s', slot, original_value, value)

    environment.storage.set_storage(environment.message.account, slot, value)

    gas_fn = environment.evm.get_sstore_gas_fn()
    gas_cost, gas_refund = gas_fn(original_value, value)

    environment.state.gas_meter.consume_gas(gas_cost)
    environment.state.gas_meter.refund_gas(gas_refund)


def sload(environment):
    slot_as_bytes = environment.state.stack.pop()
    slot = big_endian_to_int(slot_as_bytes)

    value = environment.storage.get_storage(environment.message.account, slot)
    environment.state.stack.push(value)

    logger.info('SLOAD: (%s) -> %s', slot, value)
