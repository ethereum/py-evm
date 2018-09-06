from trinity.chains import (
    CustomChain,
)

from trinity.chains import (
    CustomLightDispatchChain,
)
from trinity.nodes.light import LightNode
from trinity.nodes.full import FullNode


class CustomFullNode(FullNode):
    chain_class = CustomChain


class CustomLightNode(LightNode):
    chain_class = CustomLightDispatchChain
