from evm.p2p.lightchain import LightChain
from evm.chains.mainnet import MAINNET_VM_CONFIGURATION
from evm.chains.ropsten import ROPSTEN_NETWORK_ID


RopstenLightChain = LightChain.configure(
    name='RopstenLightChain',
    vm_configuration=MAINNET_VM_CONFIGURATION,  # TODO: use real ropsten configuration
    network_id=ROPSTEN_NETWORK_ID,
)
