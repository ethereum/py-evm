from evm.chains.ropsten import (
    RopstenChain,
    BYZANTIUM_ROPSTEN_BLOCK
)

from trinity.chains.ropsten import (
    RopstenLightDispatchChain,
)
from trinity.nodes.light import LightNode
from trinity.nodes.full import FullNode


class RopstenFullNode(FullNode):
    chain_class = RopstenChain
    initial_tx_validation_block_number = BYZANTIUM_ROPSTEN_BLOCK


class RopstenLightNode(LightNode):
    chain_class = RopstenLightDispatchChain
    initial_tx_validation_block_number = BYZANTIUM_ROPSTEN_BLOCK
