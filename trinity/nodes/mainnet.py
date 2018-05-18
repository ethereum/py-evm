from trinity.chains.mainnet import MainnetLightDispatchChain
from trinity.nodes.light import LightNode


class MainnetLightNode(LightNode):
    chain_class = MainnetLightDispatchChain
