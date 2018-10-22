from eth.chains.base import Chain

from trinity.chains.coro import AsyncChainMixin


class FullChain(Chain, AsyncChainMixin):
    pass
