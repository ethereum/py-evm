from evm.chains.ropsten import (
    RopstenChain,
)

from trinity.chains.ropsten import (
    RopstenLightDispatchChain,
)
from trinity.nodes.light import LightNode
from trinity.nodes.full import FullNode


class RopstenFullNode(FullNode):
    chain_class = RopstenChain


class RopstenLightNode(LightNode):
    chain_class = RopstenLightDispatchChain
