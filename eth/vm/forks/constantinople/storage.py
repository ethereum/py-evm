from functools import (
    partial,
)

from eth.vm.logic.storage import (
    NetSStoreGasSchedule,
    net_sstore,
)

GAS_SCHEDULE_EIP1283 = NetSStoreGasSchedule(
    sload_gas=200,
    sstore_set_gas=20000,
    sstore_reset_gas=5000,
    sstore_clears_schedule=15000,
)


sstore_eip1283 = partial(net_sstore, GAS_SCHEDULE_EIP1283)
