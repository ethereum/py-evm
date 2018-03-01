from evm.chains.mainnet import MAINNET_VM_CONFIGURATION
from evm.chains.ropsten import ROPSTEN_NETWORK_ID

from p2p.lightchain import LightChain

from typing import Type

RopstenLightChain: Type[LightChain] = LightChain.configure(
    __name__='RopstenLightChain',
    vm_configuration=MAINNET_VM_CONFIGURATION,  # TODO: use real ropsten configuration
    network_id=ROPSTEN_NETWORK_ID,
)
