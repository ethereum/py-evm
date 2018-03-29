from evm.vm.forks import ByzantiumVM

from p2p.lightchain import LightChain

from typing import Type


DEV_VM_CONFIGURATION = (
    # Note: All forks are excluded other than the latest mainnet rules
    (0, ByzantiumVM),
)


DevLightChain: Type[LightChain] = LightChain.configure(
    __name__='DevLightChain',
    vm_configuration=DEV_VM_CONFIGURATION,
)
