from evm import constants
from evm import EVM

from evm.vm.flavors.frontier import FrontierVM
from evm.vm.flavors.homestead import HomesteadVM

from evm.validation import (
    validate_vm_block_ranges,
)


FRONTIER_BLOCK_RANGE = (None, constants.FRONTIER_MAINNET_FINAL_BLOCK)
HOMESTEAD_BLOCK_RANGE = (constants.HOMESTEAD_MAINNET_BLOCK, None)


# sanity check
validate_vm_block_ranges((
    FRONTIER_BLOCK_RANGE,
    HOMESTEAD_BLOCK_RANGE,
))


MAINNET_BLOCK_RANGES = (
    (FRONTIER_BLOCK_RANGE, FrontierVM),
    (HOMESTEAD_BLOCK_RANGE, HomesteadVM),
)


MainnetEVM = EVM.configure(
    'MainnetEVM',
    vm_block_ranges=MAINNET_BLOCK_RANGES,
)
