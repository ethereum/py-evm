from eth.chains.ropsten import (
    BaseRopstenChain,
    RopstenChain
)

from trinity.chains.coro import AsyncChainMixin
from trinity.chains.light import LightDispatchChain


class RopstenFullChain(RopstenChain, AsyncChainMixin):
    pass


class RopstenLightDispatchChain(BaseRopstenChain, LightDispatchChain):
    pass
