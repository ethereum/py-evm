import asyncio
from typing import Type

from eth_keys.datatypes import PrivateKey

from p2p.discovery import DiscoveryService, PreferredNodeDiscoveryProtocol
from p2p.kademlia import Address
from p2p.peer import (
    PeerPool,
)

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
from trinity.protocol.les.peer import LESPeer
from trinity.sync.light.chain import LightChainSyncer
from trinity.sync.light.service import LightPeerChain


class LightNode(Node):
    chain_class: Type[LightDispatchChain] = None

    _chain: LightDispatchChain = None
    _peer_chain: LightPeerChain = None
    _p2p_server: LightChainSyncer = None

    network_id: int = None
    nodekey: PrivateKey = None

    def __init__(self, plugin_manager: PluginManager, chain_config: ChainConfig) -> None:
        super().__init__(plugin_manager, chain_config)

        self.network_id = chain_config.network_id
        self.nodekey = chain_config.nodekey

        self._port = chain_config.port
        self._discovery_proto = PreferredNodeDiscoveryProtocol(
            chain_config.nodekey,
            Address('0.0.0.0', chain_config.port, chain_config.port),
            bootstrap_nodes=chain_config.bootstrap_nodes,
            preferred_nodes=chain_config.preferred_nodes,
        )
        self._peer_pool = self._create_peer_pool(chain_config)
        self._discovery = DiscoveryService(
            self._discovery_proto, self._peer_pool, self.cancel_token)
        self._peer_chain = LightPeerChain(self.headerdb, self._peer_pool, self.cancel_token)
        self.add_service(self._discovery)
        self.add_service(self._peer_pool)
        self.add_service(self._peer_chain)
        self.notify_resource_available()

    async def _run(self) -> None:
        # TODO add a datagram endpoint service that can be added with self.add_service
        self.logger.info(
            "enode://%s@%s:%s",
            self.nodekey.public_key.to_hex()[2:],
            '0.0.0.0',
            self._port,
        )
        self.logger.info('network: %s', self.network_id)
        self.logger.info('peers: max_peers=%s', self._peer_pool.max_peers)
        transport, _ = await asyncio.get_event_loop().create_datagram_endpoint(
            lambda: self._discovery_proto,
            local_addr=('0.0.0.0', self._port)
        )
        await super()._run()

    def get_chain(self) -> LightDispatchChain:
        if self._chain is None:
            if self.chain_class is None:
                raise AttributeError("LightNode subclass must set chain_class")
            self._chain = self.chain_class(self._headerdb, peer_chain=self._peer_chain)

        return self._chain

    def get_p2p_server(self) -> LightChainSyncer:
        if self._p2p_server is None:
            if self.chain_class is None:
                raise AttributeError("LightNode subclass must set chain_class")
            self._p2p_server = LightChainSyncer(
                self.db_manager.get_chain(),  # type: ignore
                self._headerdb,
                self._peer_pool,
                self.cancel_token)
        return self._p2p_server

    def get_peer_pool(self) -> PeerPool:
        return self._peer_pool

    def _create_peer_pool(self, chain_config: ChainConfig) -> PeerPool:
        return PeerPool(
            LESPeer,
            self.headerdb,
            chain_config.network_id,
            chain_config.nodekey,
            self.chain_class.vm_configuration,
            token=self.cancel_token,
        )
