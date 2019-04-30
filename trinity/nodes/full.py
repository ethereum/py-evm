from typing import Type

from p2p.peer_pool import BasePeerPool

from trinity.chains.full import FullChain
from trinity.config import TrinityConfig
from trinity.endpoint import TrinityEventBusEndpoint
from trinity.server import FullServer

from .base import Node


class FullNode(Node):
    _chain: FullChain = None
    _p2p_server: FullServer = None

    def __init__(self, event_bus: TrinityEventBusEndpoint, trinity_config: TrinityConfig) -> None:
        super().__init__(event_bus, trinity_config)
        self._bootstrap_nodes = trinity_config.bootstrap_nodes
        self._preferred_nodes = trinity_config.preferred_nodes
        self._node_key = trinity_config.nodekey
        self._node_port = trinity_config.port
        self._max_peers = trinity_config.max_peers

    @property
    def chain_class(self) -> Type[FullChain]:
        return self.chain_config.full_chain_class

    def get_chain(self) -> FullChain:
        return self.get_full_chain()

    def get_p2p_server(self) -> FullServer:
        if self._p2p_server is None:
            manager = self.db_manager
            self._p2p_server = FullServer(
                privkey=self._node_key,
                port=self._node_port,
                chain=self.get_full_chain(),
                chaindb=manager.get_chaindb(),  # type: ignore
                headerdb=self.headerdb,
                base_db=manager.get_db(),  # type: ignore
                network_id=self._network_id,
                max_peers=self._max_peers,
                bootstrap_nodes=self._bootstrap_nodes,
                preferred_nodes=self._preferred_nodes,
                token=self.cancel_token,
                event_bus=self.event_bus,
            )
        return self._p2p_server

    def get_peer_pool(self) -> BasePeerPool:
        return self.get_p2p_server().peer_pool
