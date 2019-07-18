from eth_utils import (
    encode_hex,
)

from eth.vm.computation import BaseComputation
from eth.vm.forks.constantinople import (
    constants
)


def sstore_eip1283(computation: BaseComputation) -> None:
    slot, value = computation.stack_pop_ints(2)

    current_value = computation.state.get_storage(
        address=computation.msg.storage_address,
        slot=slot,
    )

    original_value = computation.state.get_storage(
        address=computation.msg.storage_address,
        slot=slot,
        from_journal=False
    )

    gas_refund = 0

    if current_value == value:
        gas_cost = constants.GAS_SSTORE_EIP1283_NOOP
    else:
        if original_value == current_value:
            if original_value == 0:
                gas_cost = constants.GAS_SSTORE_EIP1283_INIT
            else:
                gas_cost = constants.GAS_SSTORE_EIP1283_CLEAN

                if value == 0:
                    gas_refund += constants.GAS_SSTORE_EIP1283_CLEAR_REFUND
        else:
            gas_cost = constants.GAS_SSTORE_EIP1283_NOOP

            if original_value != 0:
                if current_value == 0:
                    gas_refund -= constants.GAS_SSTORE_EIP1283_CLEAR_REFUND
                if value == 0:
                    gas_refund += constants.GAS_SSTORE_EIP1283_CLEAR_REFUND

            if original_value == value:
                if original_value == 0:
                    gas_refund += constants.GAS_SSTORE_EIP1283_RESET_CLEAR_REFUND
                else:
                    gas_refund += constants.GAS_SSTORE_EIP1283_RESET_REFUND

    computation.consume_gas(
        gas_cost,
        reason="SSTORE: {0}[{1}] -> {2} (current: {3} / original: {4})".format(
            encode_hex(computation.msg.storage_address),
            slot,
            value,
            current_value,
            original_value,
        )
    )

    if gas_refund:
        computation.refund_gas(gas_refund)

    computation.state.set_storage(
        address=computation.msg.storage_address,
        slot=slot,
        value=value,
    )
