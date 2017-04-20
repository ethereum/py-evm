from evm import constants
from evm.vm.evm import MetaEVM

from evm.vm.flavors.frontier import FrontierEVM
from evm.vm.flavors.homestead import HomesteadEVM

from evm.validation import (
    validate_evm_block_ranges,
)


FRONTIER_BLOCK_RANGE = (None, constants.FRONTIER_MAINNET_FINAL_BLOCK)
HOMESTEAD_BLOCK_RANGE = (constants.HOMESTEAD_MAINNET_BLOCK, None)


# sanity check
validate_evm_block_ranges((
    FRONTIER_BLOCK_RANGE,
    HOMESTEAD_BLOCK_RANGE,
))


MainnetEVM = MetaEVM.configure(
    'MainnetEVM',
    evm_block_ranges=(
        (FRONTIER_BLOCK_RANGE, FrontierEVM),
        (HOMESTEAD_BLOCK_RANGE, HomesteadEVM),
    ),
)
