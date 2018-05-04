from evm.chains.mainnet import (
    BaseMainnetChain,
)

from p2p.lightchain import LightChain


class MainnetLightChain(BaseMainnetChain, LightChain):
    pass
