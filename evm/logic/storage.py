import logging

from evm import constants


logger = logging.getLogger('evm.logic.storage')


def sstore(computation):
    slot = computation.stack.pop(type_hint=constants.UINT256)

    original_value = computation.storage.get_storage(computation.msg.storage_address, slot)
    value = computation.stack.pop(type_hint=constants.BYTES)

    logger.info('SSTORE: (%s) %s -> %s', slot, original_value, value)

    gas_fn = computation.evm.get_sstore_gas_fn()
    gas_cost, gas_refund = gas_fn(original_value, value)

    computation.gas_meter.consume_gas(gas_cost, reason="SSTORE:{0}".format(slot))
    computation.gas_meter.refund_gas(gas_refund)

    computation.storage.set_storage(computation.msg.storage_address, slot, value)


def sload(computation):
    slot = computation.stack.pop(type_hint=constants.UINT256)

    value = computation.storage.get_storage(computation.msg.storage_address, slot)
    computation.stack.push(value)

    logger.info('SLOAD: (%s) -> %s', slot, value)
