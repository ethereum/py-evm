from eth.chains.base import (
    BaseChain
)

from p2p.peer import BasePeerPool

from trinity.config import ChainConfig
from trinity.extensibility import PluginManager
from trinity.server import FullServer

from .base import Node


class FullNode(Node):
    _chain: BaseChain = None
    _p2p_server: FullServer = None

    def __init__(self, plugin_manager: PluginManager, chain_config: ChainConfig) -> None:
        super().__init__(plugin_manager, chain_config)
        self._bootstrap_nodes = chain_config.bootstrap_nodes
        self._preferred_nodes = chain_config.preferred_nodes
        self._network_id = chain_config.network_id
        self._node_key = chain_config.nodekey
        self._node_port = chain_config.port
        self._max_peers = chain_config.max_peers
        self.notify_resource_available()

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
                event_bus=self._plugin_manager.event_bus_endpoint
            )
        return self._p2p_server

    def get_peer_pool(self) -> BasePeerPool:
        return self.get_p2p_server().peer_pool
