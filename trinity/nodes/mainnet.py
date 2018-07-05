from evm.chains.mainnet import (
    MainnetChain,
)

from trinity.chains.mainnet import (
    MainnetLightDispatchChain,
)
from trinity.nodes.light import LightNode
from trinity.nodes.full import FullNode


class MainnetFullNode(FullNode):
    chain_class = MainnetChain


class MainnetLightNode(LightNode):
    chain_class = MainnetLightDispatchChain
