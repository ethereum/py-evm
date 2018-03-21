from evm.chains.ropsten import (
    ROPSTEN_NETWORK_ID,
    ROPSTEN_VM_CONFIGURATION,
)

from p2p.lightchain import LightChain

from typing import Type


RopstenLightChain: Type[LightChain] = LightChain.configure(
    __name__='RopstenLightChain',
    vm_configuration=ROPSTEN_VM_CONFIGURATION,
    network_id=ROPSTEN_NETWORK_ID,
)
