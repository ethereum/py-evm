from eth_typing import (
    Address,
)
from eth_utils.toolz import (
    curry,
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
from eth.vm import (
    mnemonics,
)
from eth.vm.forks.istanbul.storage import (
    GAS_SCHEDULE_EIP2200,
    sstore_eip2200_generic,
)
from eth.vm.logic.call import (
    CallByzantium,
    CallCodeEIP150,
    DelegateCallEIP150,
    StaticCall,
)
from eth.vm.logic.context import (
    consume_extcodecopy_word_cost,
    extcodecopy_execute,
    push_balance_of_address,
)
from eth.vm.logic.storage import (
    NetSStoreGasSchedule,
)
from eth.vm.logic.system import (
    Create2,
    CreateByzantium,
    CreateOpcodeStackData,
    selfdestruct_eip161_on_address,
)

from . import (
    constants as berlin_constants,
)


def _mark_address_warm(computation: ComputationAPI, address: Address) -> bool:
    """
    Mark the given address as warm if it was not previously.

    :return was_cold: True if the account was not previously accessed
        during this transaction
    """
    if computation.state.is_address_warm(address):
        return False
    else:
        computation.state.mark_address_warm(address)
        return True


def _account_load_cost(was_cold: bool) -> int:
    if was_cold:
        return berlin_constants.COLD_ACCOUNT_ACCESS_COST
    else:
        return berlin_constants.WARM_STORAGE_READ_COST


def _consume_gas_for_account_load(
    computation: ComputationAPI, address: Address, reason: str
) -> None:
    was_cold = _mark_address_warm(computation, address)
    gas_cost = _account_load_cost(was_cold)
    computation.consume_gas(gas_cost, reason=reason)


def _mark_storage_warm(computation: ComputationAPI, slot: int) -> bool:
    """
    :return was_cold: True if the storage slot was not previously accessed
        during this transaction
    """
    storage_address = computation.msg.storage_address
    if computation.state.is_storage_warm(storage_address, slot):
        return False
    else:
        computation.state.mark_storage_warm(storage_address, slot)
        return True


def balance_eip2929(computation: ComputationAPI) -> None:
    address = force_bytes_to_address(computation.stack_pop1_bytes())
    _consume_gas_for_account_load(computation, address, mnemonics.BALANCE)
    push_balance_of_address(address, computation)


def extcodesize_eip2929(computation: ComputationAPI) -> None:
    address = force_bytes_to_address(computation.stack_pop1_bytes())
    _consume_gas_for_account_load(computation, address, mnemonics.EXTCODEHASH)

    code_size = len(computation.state.get_code(address))
    computation.stack_push_int(code_size)


def extcodecopy_eip2929(computation: ComputationAPI) -> None:
    address, size = extcodecopy_execute(computation)
    consume_extcodecopy_word_cost(computation, size)
    _consume_gas_for_account_load(computation, address, mnemonics.EXTCODECOPY)


def extcodehash_eip2929(computation: ComputationAPI) -> None:
    """
    Return the code hash for a given address.
    EIP: https://github.com/ethereum/EIPs/blob/master/EIPS/eip-1052.md
    """
    address = force_bytes_to_address(computation.stack_pop1_bytes())
    state = computation.state

    _consume_gas_for_account_load(computation, address, mnemonics.EXTCODEHASH)

    if state.account_is_empty(address):
        computation.stack_push_bytes(constants.NULL_BYTE)
    else:
        computation.stack_push_bytes(state.get_code_hash(address))


def sload_eip2929(computation: ComputationAPI) -> None:
    slot = computation.stack_pop1_int()

    if _mark_storage_warm(computation, slot):
        gas_cost = berlin_constants.COLD_SLOAD_COST
    else:
        gas_cost = berlin_constants.WARM_STORAGE_READ_COST
    computation.consume_gas(gas_cost, reason=mnemonics.SLOAD)

    value = computation.state.get_storage(
        address=computation.msg.storage_address,
        slot=slot,
    )
    computation.stack_push_int(value)


GAS_SCHEDULE_EIP2929 = GAS_SCHEDULE_EIP2200._replace(
    sload_gas=berlin_constants.WARM_STORAGE_READ_COST,
    sstore_reset_gas=5000 - berlin_constants.COLD_SLOAD_COST,
)


@curry
def sstore_eip2929_generic(
    gas_schedule: NetSStoreGasSchedule,
    computation: ComputationAPI,
) -> int:
    slot = sstore_eip2200_generic(gas_schedule, computation)

    if _mark_storage_warm(computation, slot):
        gas_cost = berlin_constants.COLD_SLOAD_COST
        computation.consume_gas(
            gas_cost, reason=f"Implicit SLOAD during {mnemonics.SSTORE}"
        )

    return slot


sstore_eip2929 = sstore_eip2929_generic(GAS_SCHEDULE_EIP2929)


class LoadFeeByCacheWarmth:
    def get_account_load_fee(
        self,
        computation: ComputationAPI,
        code_address: Address,
    ) -> int:
        was_cold = _mark_address_warm(computation, code_address)
        return _account_load_cost(was_cold)


class CallEIP2929(LoadFeeByCacheWarmth, CallByzantium):
    pass


class CallCodeEIP2929(LoadFeeByCacheWarmth, CallCodeEIP150):
    pass


class DelegateCallEIP2929(LoadFeeByCacheWarmth, DelegateCallEIP150):
    pass


class StaticCallEIP2929(LoadFeeByCacheWarmth, StaticCall):
    pass


def selfdestruct_eip2929(computation: ComputationAPI) -> None:
    beneficiary = force_bytes_to_address(computation.stack_pop1_bytes())

    if _mark_address_warm(computation, beneficiary):
        gas_cost = berlin_constants.COLD_ACCOUNT_ACCESS_COST
        computation.consume_gas(
            gas_cost,
            reason=f"Implicit account load during {mnemonics.SELFDESTRUCT}",
        )

    selfdestruct_eip161_on_address(computation, beneficiary)


class CreateEIP2929(CreateByzantium):
    def generate_contract_address(
        self,
        stack_data: CreateOpcodeStackData,
        call_data: bytes,
        computation: ComputationAPI,
    ) -> Address:
        address = super().generate_contract_address(stack_data, call_data, computation)
        computation.state.mark_address_warm(address)
        return address


class Create2EIP2929(Create2):
    def generate_contract_address(
        self,
        stack_data: CreateOpcodeStackData,
        call_data: bytes,
        computation: ComputationAPI,
    ) -> Address:
        address = super().generate_contract_address(stack_data, call_data, computation)
        computation.state.mark_address_warm(address)
        return address
