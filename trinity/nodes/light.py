from typing import Type

from eth_keys.datatypes import PrivateKey
from p2p.discovery import DiscoveryProtocol
from p2p.kademlia import Address
from p2p.lightchain import LightPeerChain
from p2p.peer import (
    LESPeer,
    PeerPool,
    PreferredNodePeerPool,
)
from p2p.service import (
    BaseService,
)

from trinity.chains.light import (
    LightDispatchChain,
)
from trinity.nodes.base import Node
from trinity.utils.chains import (
    ChainConfig,
)


class LightNode(Node):
    chain_class: Type[LightDispatchChain] = None

    _chain: LightDispatchChain = None

    def __init__(self, chain_config: ChainConfig) -> None:
        super().__init__(chain_config)

        self._peer_pool = self._create_peer_pool(chain_config)
        self.add_service(self._peer_pool)

    def get_chain(self) -> LightDispatchChain:
        if self._chain is None:
            if self.chain_class is None:
                raise AttributeError("LightNode subclass must set chain_class")
            self._chain = self.chain_class(self._headerdb, peer_chain=self.get_peer_service())

        return self._chain

    def get_peer_service(self) -> BaseService:
        if self._peer_service is None:
            self._peer_service = LightPeerChain(self.headerdb, self._peer_pool)
        return self._peer_service

    def _create_peer_pool(self, chain_config: ChainConfig) -> PeerPool:
        discovery = DiscoveryProtocol(
            chain_config.nodekey,
            Address('0.0.0.0', chain_config.port, chain_config.port),
            bootstrap_nodes=chain_config.bootstrap_nodes,
        )
        return PreferredNodePeerPool(
            LESPeer,
            self.headerdb,
            chain_config.network_id,
            chain_config.nodekey,
            discovery,
            preferred_nodes=chain_config.preferred_nodes,
        )
