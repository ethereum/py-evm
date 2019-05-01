from eth_utils import (
    encode_hex,
)
from eth import constants

from eth.vm.computation import BaseComputation


def sstore(computation: BaseComputation) -> None:
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

    computation.consume_gas(gas_cost, reason="SSTORE: {0}[{1}] -> {2} ({3})".format(
        encode_hex(computation.msg.storage_address),
        slot,
        value,
        current_value,
    ))

    if gas_refund:
        computation.refund_gas(gas_refund)

    computation.state.set_storage(
        address=computation.msg.storage_address,
        slot=slot,
        value=value,
    )


def sload(computation: BaseComputation) -> None:
    slot = computation.stack_pop1_int()

    value = computation.state.get_storage(
        address=computation.msg.storage_address,
        slot=slot,
    )
    computation.stack_push_int(value)
