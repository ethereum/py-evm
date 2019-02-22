from typing import (
    cast,
    Type,
)

from eth_keys.datatypes import PrivateKey
from eth_utils import (
    ValidationError,
)

from p2p.peer_pool import BasePeerPool

from trinity.chains.light import (
    LightDispatchChain,
)
from trinity.config import (
    TrinityConfig,
)
from trinity.endpoint import TrinityEventBusEndpoint
from trinity.nodes.base import Node
from trinity.protocol.les.peer import LESPeerPool
from trinity.server import LightServer
from trinity.sync.light.service import LightPeerChain


class LightNode(Node):
    _chain: LightDispatchChain = None
    _peer_chain: LightPeerChain = None
    _p2p_server: LightServer = None

    network_id: int = None
    nodekey: PrivateKey = None

    def __init__(self, event_bus: TrinityEventBusEndpoint, trinity_config: TrinityConfig) -> None:
        super().__init__(event_bus, trinity_config)

        self._nodekey = trinity_config.nodekey
        self._port = trinity_config.port
        self._max_peers = trinity_config.max_peers
        self._bootstrap_nodes = trinity_config.bootstrap_nodes
        self._preferred_nodes = trinity_config.preferred_nodes

        self._peer_chain = LightPeerChain(
            self.headerdb,
            cast(LESPeerPool, self.get_peer_pool()),
            token=self.cancel_token,
        )

    @property
    def chain_class(self) -> Type[LightDispatchChain]:
        return self.chain_config.light_chain_class

    async def _run(self) -> None:
        self.run_daemon(self._peer_chain)
        await super()._run()

    def get_chain(self) -> LightDispatchChain:
        if self._chain is None:
            if self.chain_class is None:
                raise AttributeError("LightNode subclass must set chain_class")
            elif self._peer_chain is None:
                raise ValidationError("peer chain is not initialized!")
            else:
                self._chain = self.chain_class(self.headerdb, peer_chain=self._peer_chain)

        return self._chain

    def get_p2p_server(self) -> LightServer:
        if self._p2p_server is None:
            manager = self.db_manager
            self._p2p_server = LightServer(
                privkey=self._nodekey,
                port=self._port,
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
