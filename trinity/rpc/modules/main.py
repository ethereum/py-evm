from eth.chains.base import (
    BaseChain
)

from trinity.protocol.common.peer import (
    TrinityPeerPool,
)


class RPCModule:
    _chain = None

    def __init__(self, chain: BaseChain, peer_pool: TrinityPeerPool) -> None:
        self._chain = chain
        self._peer_pool = peer_pool

    def set_chain(self, chain: BaseChain) -> None:
        self._chain = chain
