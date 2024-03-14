from eth_utils import (
    encode_hex,
)

from eth import (
    constants,
)
from eth._utils.address import (
    force_bytes_to_address,
)
from eth.abc import (
    ComputationAPI,
)
from eth.exceptions import (
    Halt,
)
from eth.vm import (
    mnemonics,
)
from eth.vm.forks.berlin import (
    constants as berlin_constants,
)
from eth.vm.forks.berlin.logic import (
    _mark_address_warm,
    selfdestruct_eip2929,
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
    if computation.msg.storage_address in computation.contracts_created:
        # allow contract to selfdestruct
        selfdestruct_eip2929(computation)
    else:
        # disallow contract to selfdestruct but all other logic remains the same
        beneficiary = force_bytes_to_address(computation.stack_pop1_bytes())

        if _mark_address_warm(computation, beneficiary):
            gas_cost = berlin_constants.COLD_ACCOUNT_ACCESS_COST
            computation.consume_gas(
                gas_cost,
                reason=f"Implicit account load during {mnemonics.SELFDESTRUCT}",
            )

        # # from vm/logic/system.py -> selfdestruct_eip161_on_address
        is_dead = not computation.state.account_exists(
            beneficiary
        ) or computation.state.account_is_empty(beneficiary)
        if is_dead and computation.state.get_balance(computation.msg.storage_address):
            computation.consume_gas(
                constants.GAS_SELFDESTRUCT_NEWACCOUNT,
                reason=mnemonics.SELFDESTRUCT,
            )

        # transfer contract balance to beneficiary
        contract_balance = computation.state.get_balance(
            computation.msg.storage_address
        )
        computation.state.delta_balance(beneficiary, contract_balance)
        computation.state.delta_balance(
            computation.msg.storage_address, -1 * contract_balance
        )

        computation.logger.debug2(
            f"SELFDESTRUCT: {encode_hex(computation.msg.storage_address)} "
            f"({contract_balance}) -> {encode_hex(beneficiary)}"
        )
        raise Halt("SELFDESTRUCT")
