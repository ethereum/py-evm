from evm import constants
from evm.chains.chain import Chain

from evm.vm.forks import (
    EIP150VM,
    FrontierVM,
    HomesteadVM,
)


MainnetChain = Chain.configure(
    'MainnetChain',
    vm_configuration=(
        (0, FrontierVM),
        (constants.HOMESTEAD_MAINNET_BLOCK, HomesteadVM),
        (constants.EIP150_MAINNET_BLOCK, EIP150VM)
    )
)
