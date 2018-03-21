from evm.chains.mainnet import (
    MAINNET_NETWORK_ID,
    MAINNET_VM_CONFIGURATION,
)

from p2p.lightchain import LightChain

from typing import Type


MainnetLightChain: Type[LightChain] = LightChain.configure(
    __name__='MainnetLightChain',
    vm_configuration=MAINNET_VM_CONFIGURATION,
    network_id=MAINNET_NETWORK_ID,
)
