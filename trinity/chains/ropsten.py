from eth.chains.ropsten import (
    BaseRopstenChain,
)

from trinity.chains.light import LightDispatchChain


class RopstenLightDispatchChain(BaseRopstenChain, LightDispatchChain):
    pass
