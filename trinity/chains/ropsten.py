# TODO: need to use appropriate block numbers for ropsten network
from evm.chains.mainnet import MAINNET_VM_CONFIGURATION
from evm.chains.ropsten import ROPSTEN_NETWORK_ID


BaseRopstenLightChain = LightChain.configure(
    name='RopstenLightChain',
    vm_configuration=MAINNET_VM_CONFIGURATION,
    network_id=ROPSTEN_NETWORK_ID,
    #privkey=ecies.generate_privkey(),  # TODO: get from stored key.
)
