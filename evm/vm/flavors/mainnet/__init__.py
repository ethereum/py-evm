from evm import constants
from evm.vm.evm import MetaEVM

from evm.vm.flavors.frontier import FrontierEVM
from evm.vm.flavors.homestead import HomesteadEVM


MainnetEVM = MetaEVM.configure(
    'MainnetEVM',
    evm_rules=(
        ((None, constants.FRONTIER_MAINNET_FINAL_BLOCK), FrontierEVM),
        ((constants.HOMESTEAD_MAINNET_BLOCK, None), HomesteadEVM),
    ),
)
