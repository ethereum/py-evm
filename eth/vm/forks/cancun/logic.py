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
    contract_address = computation.msg.storage_address

    if contract_address in computation.contracts_created:
        if computation.logger.show_debug2:
            computation.logger.debug2(
                "Contract created within computation and allowed to self destruct: "
                f"{encode_hex(contract_address)} "
            )
        selfdestruct_eip2929(computation)
    else:
        # disallow contract to selfdestruct but all other logic remains the same
        if computation.logger.show_debug2:
            computation.logger.debug2(
                "Contract was not created within computation and thus not allowed to "
                f"self destruct: {encode_hex(contract_address)}."
            )

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
        if is_dead and computation.state.get_balance(contract_address):
            computation.consume_gas(
                constants.GAS_SELFDESTRUCT_NEWACCOUNT,
                reason=mnemonics.SELFDESTRUCT,
            )

        # transfer contract balance to beneficiary
        contract_balance = computation.state.get_balance(contract_address)
        computation.state.delta_balance(beneficiary, contract_balance)
        computation.state.delta_balance(contract_address, -1 * contract_balance)
        computation.beneficiaries.append(beneficiary)

        computation.logger.debug2(
            f"SELFDESTRUCT: {encode_hex(contract_address)} "
            f"({contract_balance}) -> {encode_hex(beneficiary)}"
        )
        raise Halt("SELFDESTRUCT")
