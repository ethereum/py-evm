from trinity.chains.mainnet import (
    MainnetFullChain,
    MainnetLightDispatchChain,
)
from trinity.nodes.light import LightNode
from trinity.nodes.full import FullNode


class MainnetFullNode(FullNode):
    chain_class = MainnetFullChain


class MainnetLightNode(LightNode):
    chain_class = MainnetLightDispatchChain
