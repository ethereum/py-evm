import logging

from evm.gas import (
    COST_SSET,
    COST_SRESET,
    COST_SLOAD,
    REFUND_SCLEAR,
)
from evm.utils.numeric import (
    big_endian_to_int,
)


logger = logging.getLogger('evm.logic.push.push')


def sstore(message, storage, state):
    slot_as_bytes = state.stack.pop()
    slot = big_endian_to_int(slot_as_bytes)

    original_value = storage.get_storage(message.account, slot)
    value = state.stack.pop()

    logger.info('SSTORE: (%s) %s -> %s', slot, original_value, value)

    storage.set_storage(message.account, slot, value)

    if original_value:
        gas_fee = COST_SRESET if value else COST_SRESET
        gas_refund = REFUND_SCLEAR if value else 0
    else:
        gas_fee = COST_SSET if value else COST_SRESET
        gas_refund = 0

    state.consume_gas(gas_fee)
    state.refund_gas(gas_refund)


def sload(message, storage, state):
    slot_as_bytes = state.stack.pop()
    slot = big_endian_to_int(slot_as_bytes)

    value = storage.get_storage(message.account, slot)
    state.stack.push(value)

    logger.info('SLOAD: (%s) -> %s', slot, value)

    state.consume_gas(COST_SLOAD)
