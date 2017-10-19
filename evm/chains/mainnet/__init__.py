from evm import constants
from evm.chains.chain import Chain

from evm.vm.forks import (
    EIP150VM,
    FrontierVM,
    HomesteadVM,
)


MAINNET_VM_CONFIGURATION = (
    (0, FrontierVM),
    (constants.HOMESTEAD_MAINNET_BLOCK, HomesteadVM),
    (constants.EIP150_MAINNET_BLOCK, EIP150VM),
)


MainnetChain = Chain.configure(
    'MainnetChain',
    vm_configuration=MAINNET_VM_CONFIGURATION,
    network_id=1,
)
