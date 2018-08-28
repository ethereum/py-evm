from eth.chains.base import (
    BaseChain
)

from lahja import (
    Endpoint
)


class RPCModule:
    _chain = None

    def __init__(self, chain: BaseChain, event_bus: Endpoint) -> None:
        self._chain = chain
        self._event_bus = event_bus

    def set_chain(self, chain: BaseChain) -> None:
        self._chain = chain
