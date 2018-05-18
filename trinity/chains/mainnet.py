from evm.chains.mainnet import (
    BaseMainnetChain,
)

from p2p.lightchain import LightPeerChain


class MainnetLightPeerChain(BaseMainnetChain, LightPeerChain):
    pass
