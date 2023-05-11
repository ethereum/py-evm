from typing import (
    NamedTuple,
)

from eth_utils import (
    encode_hex,
)

from eth import (
    constants,
)
from eth.abc import (
    ComputationAPI,
)


def sstore(computation: ComputationAPI) -> None:
    slot, value = computation.stack_pop_ints(2)

    current_value = computation.state.get_storage(
        address=computation.msg.storage_address,
        slot=slot,
    )

    is_currently_empty = not bool(current_value)
    is_going_to_be_empty = not bool(value)

    if is_currently_empty:
        gas_refund = 0
    elif is_going_to_be_empty:
        gas_refund = constants.REFUND_SCLEAR
    else:
        gas_refund = 0

    if is_currently_empty and is_going_to_be_empty:
        gas_cost = constants.GAS_SRESET
    elif is_currently_empty:
        gas_cost = constants.GAS_SSET
    elif is_going_to_be_empty:
        gas_cost = constants.GAS_SRESET
    else:
        gas_cost = constants.GAS_SRESET

    computation.consume_gas(
        gas_cost,
        reason=(
            f"SSTORE: {encode_hex(computation.msg.storage_address)}"
            f"[{slot}] -> {value} ({current_value})"
        ),
    )

    if gas_refund:
        computation.refund_gas(gas_refund)

    computation.state.set_storage(
        address=computation.msg.storage_address,
        slot=slot,
        value=value,
    )


def sload(computation: ComputationAPI) -> None:
    slot = computation.stack_pop1_int()

    value = computation.state.get_storage(
        address=computation.msg.storage_address,
        slot=slot,
    )
    computation.stack_push_int(value)


class NetSStoreGasSchedule(NamedTuple):
    # the gas cost when nothing changes (eg~ dirty->dirty, clean->clean, etc)
    sload_gas: int

    # a brand new value, where none previously existed, aka init or set
    sstore_set_gas: int

    # a change to a value when the value was previously unchanged, aka clean, reset
    sstore_reset_gas: int

    # the refund for removing a value, aka: clear_refund
    sstore_clears_schedule: int


def net_sstore(gas_schedule: NetSStoreGasSchedule, computation: ComputationAPI) -> int:
    """
    :return slot: where the new value was stored
    """
    slot, value = computation.stack_pop_ints(2)

    current_value = computation.state.get_storage(
        address=computation.msg.storage_address,
        slot=slot,
    )

    original_value = computation.state.get_storage(
        address=computation.msg.storage_address, slot=slot, from_journal=False
    )

    gas_refund = 0

    if current_value == value:
        gas_cost = gas_schedule.sload_gas
    else:
        if original_value == current_value:
            if original_value == 0:
                gas_cost = gas_schedule.sstore_set_gas
            else:
                gas_cost = gas_schedule.sstore_reset_gas

                if value == 0:
                    gas_refund += gas_schedule.sstore_clears_schedule
        else:
            gas_cost = gas_schedule.sload_gas

            if original_value != 0:
                if current_value == 0:
                    gas_refund -= gas_schedule.sstore_clears_schedule
                if value == 0:
                    gas_refund += gas_schedule.sstore_clears_schedule

            if original_value == value:
                if original_value == 0:
                    gas_refund += gas_schedule.sstore_set_gas - gas_schedule.sload_gas
                else:
                    gas_refund += gas_schedule.sstore_reset_gas - gas_schedule.sload_gas

    computation.consume_gas(
        gas_cost,
        reason=(
            f"SSTORE: {encode_hex(computation.msg.storage_address)}"
            f"[{slot}] -> {value} (current: {current_value} / "
            f"original: {original_value})"
        ),
    )

    if gas_refund:
        computation.refund_gas(gas_refund)

    computation.state.set_storage(
        address=computation.msg.storage_address,
        slot=slot,
        value=value,
    )
    return slot
