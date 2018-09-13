from trinity.chains.ropsten import (
    RopstenFullChain,
    RopstenLightDispatchChain,
)
from trinity.nodes.light import LightNode
from trinity.nodes.full import FullNode


class RopstenFullNode(FullNode):
    chain_class = RopstenFullChain


class RopstenLightNode(LightNode):
    chain_class = RopstenLightDispatchChain
