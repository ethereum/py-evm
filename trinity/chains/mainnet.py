from evm.chains.mainnet import (
    BaseMainnetChain,
)

from trinity.chains.light import LightDispatchChain


class MainnetLightDispatchChain(BaseMainnetChain, LightDispatchChain):
    pass
