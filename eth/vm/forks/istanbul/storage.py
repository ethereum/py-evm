from eth_utils.toolz import curry

from eth.exceptions import OutOfGas
from eth.vm.computation import MessageComputation
from eth.vm.forks.constantinople.storage import (
    GAS_SCHEDULE_EIP1283,
)
from eth.vm.forks.istanbul import (
    constants
)
from eth.vm.logic.storage import (
    NetSStoreGasSchedule,
    net_sstore,
)

GAS_SCHEDULE_EIP2200 = GAS_SCHEDULE_EIP1283._replace(
    sload_gas=constants.GAS_SLOAD_EIP1884,
)


@curry
def sstore_eip2200_generic(
    gas_schedule: NetSStoreGasSchedule,
    computation: MessageComputation,
) -> int:
    gas_remaining = computation.get_gas_remaining()
    if gas_remaining <= 2300:
        raise OutOfGas(
            "Net-metered SSTORE always fails below 2300 gas, per EIP-2200",
            gas_remaining,
        )
    else:
        return net_sstore(gas_schedule, computation)


sstore_eip2200 = sstore_eip2200_generic(GAS_SCHEDULE_EIP2200)
