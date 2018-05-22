from trinity.chains.ropsten import RopstenLightDispatchChain
from trinity.nodes.light import LightNode


class RopstenLightNode(LightNode):
    chain_class = RopstenLightDispatchChain
