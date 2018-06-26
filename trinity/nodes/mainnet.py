from evm.chains.mainnet import (
    MainnetChain,
    BYZANTIUM_MAINNET_BLOCK
)

from trinity.chains.mainnet import (
    MainnetLightDispatchChain,
)
from trinity.nodes.light import LightNode
from trinity.nodes.full import FullNode


class MainnetFullNode(FullNode):
    chain_class = MainnetChain
    initial_tx_validation_block_number = BYZANTIUM_MAINNET_BLOCK


class MainnetLightNode(LightNode):
    chain_class = MainnetLightDispatchChain
    initial_tx_validation_block_number = BYZANTIUM_MAINNET_BLOCK
