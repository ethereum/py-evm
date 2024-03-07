from eth._utils.address import (
    force_bytes_to_address,
)
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


def selfdestruct_eip6780(computation: ComputationAPI) -> None:
    force_bytes_to_address(computation.stack_pop1_bytes())
    # computation.state.mark_account_for_deletion(beneficiary)
    # computation.state.account_db.delete_account(beneficiary)
    # computation.state.account_db.persist()
