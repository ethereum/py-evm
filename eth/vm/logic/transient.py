def tstore(computation):
    address = computation.msg.storage_address
    slot, value = computation.stack_pop_ints(2)

    computation.state.set_transient_storage(address, slot, value)


def tload(computation):
    address = computation.msg.storage_address
    slot = computation.stack_pop1_int()
    state = computation.state
    value = state.get_transient_storage(address, slot)

    computation.push_int(value)
