from evm.chains.base import (
    BaseChain
)

from p2p.service import (
    BaseService,
)


class RPCModule:
    _chain = None

    def __init__(self, chain: BaseChain=None, p2p_server: BaseService=None) -> None:
        self._chain = chain
        self._p2p_server = p2p_server

    def set_chain(self, chain: BaseChain) -> None:
        self._chain = chain
