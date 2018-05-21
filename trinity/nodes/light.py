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

from trinity.chains.light import (
    LightDispatchChain,
)

from trinity.nodes.base import Node


class LightNode(Node):
    peer_chain_class = LightPeerChain
    chain_class: Type[LightDispatchChain] = None

    _chain: LightDispatchChain = None

    def get_chain(self) -> LightDispatchChain:
        if self._chain is None:
            if self.chain_class is None:
                raise AttributeError("LightNode subclass must set chain_class")
            peer_chain = self._peer_chain
            self._chain = self.chain_class(self._headerdb, peer_chain=peer_chain)

        return self._chain

    def create_peer_pool(self, network_id: int, node_key: PrivateKey) -> PeerPool:
        discovery = DiscoveryProtocol(
            chain_config.nodekey,
            Address('0.0.0.0', chain_config.port, chain_config.port),
            bootstrap_nodes=chain_config.bootstrap_nodes,
        )
        return PreferredNodePeerPool(
            LESPeer,
            self.headerdb,
            network_id,
            node_key,
            discovery,
            preferred_nodes=chain_config.preferred_nodes,
        )
