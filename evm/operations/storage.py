from evm.utils.numeric import (
    big_endian_to_int,
)


def sstore(storage, state, code_stream):
    slot_as_bytes = state.stack.pop()
    slot = big_endian_to_int(slot_as_bytes)
    value = state.stack.pop()

    storage.set_storage(state.account, slot, value)
