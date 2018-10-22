from lahja import (
    Endpoint
)

from trinity.chains.base import BaseAsyncChain


class RPCModule:
    _chain = None

    def __init__(self, chain: BaseAsyncChain, event_bus: Endpoint) -> None:
        self._chain = chain
        self._event_bus = event_bus

    def set_chain(self, chain: BaseAsyncChain) -> None:
        self._chain = chain
