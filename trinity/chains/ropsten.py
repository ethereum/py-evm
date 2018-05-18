from evm.chains.ropsten import (
    BaseRopstenChain,
)

from p2p.lightchain import LightPeerChain


class RopstenLightPeerChain(BaseRopstenChain, LightPeerChain):
    pass
