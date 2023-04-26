from eth_utils.toolz import (
    partial,
)

from eth.vm.forks.berlin import (
    constants as berlin_constants,
)
from eth.vm.forks.berlin.logic import (
    GAS_SCHEDULE_EIP2929,
    sstore_eip2929_generic,
)

SSTORE_CLEARS_SCHEDULE_EIP_3529 = (
    GAS_SCHEDULE_EIP2929.sstore_reset_gas
    + berlin_constants.ACCESS_LIST_STORAGE_KEY_COST_EIP_2930
)


GAS_SCHEDULE_EIP3529 = GAS_SCHEDULE_EIP2929._replace(
    sstore_clears_schedule=SSTORE_CLEARS_SCHEDULE_EIP_3529
)

sstore_eip3529 = partial(sstore_eip2929_generic, GAS_SCHEDULE_EIP3529)
