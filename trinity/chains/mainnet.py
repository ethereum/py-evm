from eth.chains.mainnet import (
    BaseMainnetChain,
    MainnetChain
)

from trinity.chains.coro import AsyncChainMixin
from trinity.chains.light import LightDispatchChain


class MainnetFullChain(MainnetChain, AsyncChainMixin):
    pass


class MainnetLightDispatchChain(BaseMainnetChain, LightDispatchChain):
    pass
