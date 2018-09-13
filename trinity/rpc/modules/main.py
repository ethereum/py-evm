from eth.chains.base import (
    AsyncChain
)

from lahja import (
    Endpoint
)


class RPCModule:
    _chain = None

    def __init__(self, chain: AsyncChain, event_bus: Endpoint) -> None:
        self._chain = chain
        self._event_bus = event_bus

    def set_chain(self, chain: AsyncChain) -> None:
        self._chain = chain
