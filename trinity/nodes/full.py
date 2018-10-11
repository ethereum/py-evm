from eth.chains.base import (
    BaseChain
)

from lahja import Endpoint

from p2p.peer import BasePeerPool

from trinity.config import TrinityConfig
from trinity.server import FullServer

from .base import Node


class FullNode(Node):
    _chain: BaseChain = None
    _p2p_server: FullServer = None

    def __init__(self, event_bus: Endpoint, trinity_config: TrinityConfig) -> None:
        super().__init__(event_bus, trinity_config)
        self._bootstrap_nodes = trinity_config.bootstrap_nodes
        self._preferred_nodes = trinity_config.preferred_nodes
        self._node_key = trinity_config.nodekey
        self._node_port = trinity_config.port
        self._max_peers = trinity_config.max_peers

    def get_chain(self) -> BaseChain:
        if self._chain is None:
            self._chain = self.chain_class(self.db_manager.get_db())  # type: ignore

        return self._chain

    def get_p2p_server(self) -> FullServer:
        if self._p2p_server is None:
            manager = self.db_manager
            self._p2p_server = FullServer(
                self._node_key,
                self._node_port,
                manager.get_chain(),  # type: ignore
                manager.get_chaindb(),  # type: ignore
                self.headerdb,
                manager.get_db(),  # type: ignore
                self._network_id,
                max_peers=self._max_peers,
                bootstrap_nodes=self._bootstrap_nodes,
                preferred_nodes=self._preferred_nodes,
                token=self.cancel_token,
                event_bus=self.event_bus,
            )
        return self._p2p_server

    def get_peer_pool(self) -> BasePeerPool:
        return self.get_p2p_server().peer_pool
