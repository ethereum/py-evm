from eth_typing import (
    Address,
)
from eth_utils.toolz import curry

from eth import constants
from eth._utils.address import (
    force_bytes_to_address,
)
from eth.abc import (
    ComputationAPI,
)
from eth.vm import mnemonics
from eth.vm.forks.istanbul.storage import (
    GAS_SCHEDULE_EIP2200,
    sstore_eip2200_generic,
)
from eth.vm.logic.call import (
    CallByzantium,
    StaticCall,
)
from eth.vm.logic.context import (
    consume_extcodecopy_word_cost,
    push_balance_of_address,
    extcodecopy_execute,
)
from eth.vm.logic.storage import (
    NetSStoreGasSchedule,
)

from . import constants as berlin_constants


def _mark_address_warm(computation: ComputationAPI, address: Address) -> int:
    """
    Mark the given address as warm if it was not previously.

    :return gas_cost: cold cost if account was not previously accessed during
        this transaction, warm cost otherwise
    """

    if computation.state.is_address_warm(address):
        return berlin_constants.WARM_STORAGE_READ_COST
    else:
        computation.state.mark_address_warm(address)
        return berlin_constants.COLD_ACCOUNT_ACCESS_COST


def _consume_gas_for_account_load(
        computation: ComputationAPI,
        address: Address,
        reason: str) -> None:
    gas_cost = _mark_address_warm(computation, address)
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
def sstore_eip2929_generic(gas_schedule: NetSStoreGasSchedule, computation: ComputationAPI) -> int:
    slot = sstore_eip2200_generic(gas_schedule, computation)

    if _mark_storage_warm(computation, slot):
        gas_cost = berlin_constants.COLD_SLOAD_COST
        computation.consume_gas(gas_cost, reason=f"Implicit SLOAD during {mnemonics.SSTORE}")

    return slot


sstore_eip2929 = sstore_eip2929_generic(GAS_SCHEDULE_EIP2929)


class CallEIP2929(CallByzantium):
    def compute_msg_extra_gas(self,
                              computation: ComputationAPI,
                              gas: int,
                              to: Address,
                              value: int) -> int:
        legacy_extra_gas = super().compute_msg_extra_gas(computation, gas, to, value)
        account_load_cost = _mark_address_warm(computation, to)
        return legacy_extra_gas + account_load_cost


class StaticCallEIP2929(StaticCall):
    def compute_msg_extra_gas(self,
                              computation: ComputationAPI,
                              gas: int,
                              to: Address,
                              value: int) -> int:
        legacy_extra_gas = super().compute_msg_extra_gas(computation, gas, to, value)
        account_load_cost = _mark_address_warm(computation, to)
        return legacy_extra_gas + account_load_cost
