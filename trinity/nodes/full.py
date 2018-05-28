from evm.chains.base import BaseChain
from p2p.peer import (
    PreferredNodePeerPool,
)
from p2p.server import Server
from p2p.service import BaseService

from trinity.nodes.base import Node
from trinity.config import (
    ChainConfig,
)


class FullNode(Node):
    _chain: BaseChain = None
    _p2p_server: BaseService = None

    def __init__(self, chain_config: ChainConfig) -> None:
        super().__init__(chain_config)

        self._bootstrap_nodes = chain_config.bootstrap_nodes
        self._network_id = chain_config.network_id
        self._node_key = chain_config.nodekey
        self._node_port = chain_config.port

    def get_chain(self):
        if self._chain is None:
            self._chain = self.chain_class(self.db_manager.get_db())

        return self._chain

    def get_p2p_server(self) -> BaseService:
        if self._p2p_server is None:
            manager = self.db_manager
            self._p2p_server = Server(
                self._node_key,
                self._node_port,
                manager.get_chain(),  # type: ignore
                manager.get_chaindb(),  # type: ignore
                self.headerdb,
                manager.get_db(),  # type: ignore
                self._network_id,
                peer_pool_class=PreferredNodePeerPool,
                bootstrap_nodes=self._bootstrap_nodes,
                token=self.cancel_token,
            )
        return self._p2p_server
