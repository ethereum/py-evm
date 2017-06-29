from evm import constants
from evm import EVM

from evm.vm.flavors import (
    FrontierVM,
    HomesteadVM,
)


MainnetEVM = EVM.configure(
    'MainnetEVM',
    vm_configuration=(
        (0, FrontierVM),
        (constants.HOMESTEAD_MAINNET_BLOCK, HomesteadVM)
    )
)
