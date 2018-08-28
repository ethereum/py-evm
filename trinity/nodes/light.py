from typing import (
    cast,
    Type,
)

from eth_keys.datatypes import PrivateKey

from p2p.peer import BasePeerPool

from trinity.chains.light import (
    LightDispatchChain,
)
from trinity.config import (
    ChainConfig,
)
from trinity.extensibility import (
    PluginManager
)
from trinity.nodes.base import Node
from trinity.protocol.les.peer import LESPeerPool
from trinity.server import LightServer
from trinity.sync.light.service import LightPeerChain


class LightNode(Node):
    chain_class: Type[LightDispatchChain] = None

    _chain: LightDispatchChain = None
    _peer_chain: LightPeerChain = None
    _p2p_server: LightServer = None

    network_id: int = None
    nodekey: PrivateKey = None

    def __init__(self, plugin_manager: PluginManager, chain_config: ChainConfig) -> None:
        super().__init__(plugin_manager, chain_config)

        self._network_id = chain_config.network_id
        self._nodekey = chain_config.nodekey
        self._port = chain_config.port
        self._max_peers = chain_config.max_peers
        self._bootstrap_nodes = chain_config.bootstrap_nodes
        self._preferred_nodes = chain_config.preferred_nodes
        self._use_discv5 = chain_config.use_discv5

        self._peer_chain = LightPeerChain(
            self.headerdb,
            cast(LESPeerPool, self.get_peer_pool()),
            token=self.cancel_token,
        )
        self.notify_resource_available()

    async def _run(self) -> None:
        self.run_daemon(self._peer_chain)
        await super()._run()

    def get_chain(self) -> LightDispatchChain:
        if self._chain is None:
            if self.chain_class is None:
                raise AttributeError("LightNode subclass must set chain_class")
            self._chain = self.chain_class(self.headerdb, peer_chain=self._peer_chain)

        return self._chain

    def get_p2p_server(self) -> LightServer:
        if self._p2p_server is None:
            manager = self.db_manager
            self._p2p_server = LightServer(
                self._nodekey,
                self._port,
                manager.get_chain(),  # type: ignore
                manager.get_chaindb(),  # type: ignore
                self.headerdb,
                manager.get_db(),  # type: ignore
                self._network_id,
                max_peers=self._max_peers,
                bootstrap_nodes=self._bootstrap_nodes,
                preferred_nodes=self._preferred_nodes,
                use_discv5=self._use_discv5,
                token=self.cancel_token,
                event_bus=self._plugin_manager.event_bus_endpoint,
            )
        return self._p2p_server

    def get_peer_pool(self) -> BasePeerPool:
        return self.get_p2p_server().peer_pool
