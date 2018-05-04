from evm.chains.ropsten import (
    BaseRopstenChain,
)

from p2p.lightchain import LightChain


class RopstenLightChain(BaseRopstenChain, LightChain):
    pass
