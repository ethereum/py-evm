from evm.constants import (
    EMPTY_WORD,
)
from evm.gas import (
    COST_SSET,
    COST_SRESET,
    REFUND_SCLEAR,
)
from evm.utils.numeric import (
    big_endian_to_int,
)


def sstore(message, storage, state):
    slot_as_bytes = state.stack.pop()
    slot = big_endian_to_int(slot_as_bytes)

    original_value = storage.get_storage(message.account, slot)
    value = state.stack.pop()

    current_storage_value = storage.get_storage(message.account, slot)
    storage.set_storage(message.account, slot, value)

    if original_value == EMPTY_WORD:
        gas_fee = COST_SSET if value == EMPTY_WORD else COST_SSET
        gas_refund = 0
    else:
        gas_fee = COST_SRESET if value == EMPTY_WORD else COST_SSET
        gas_refund = REFUND_SCLEAR if value == EMPTY_WORD else 0

    state.consume_gas(gas_fee)
    state.refund_gas(gas_refund)
