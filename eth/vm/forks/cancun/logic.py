from eth.abc import (
    ComputationAPI,
)
from eth.vm.forks.byzantium.opcodes import (
    ensure_no_static,
)


@ensure_no_static
def tstore(computation: ComputationAPI) -> None:
    address = computation.msg.storage_address
    slot = computation.stack_pop1_int()
    value = computation.stack_pop1_bytes()
    computation.state.set_transient_storage(address, slot, value)


def tload(computation: ComputationAPI) -> None:
    address = computation.msg.storage_address
    slot = computation.stack_pop1_int()
    value = computation.state.get_transient_storage(address, slot)
    computation.stack_push_bytes(value)
