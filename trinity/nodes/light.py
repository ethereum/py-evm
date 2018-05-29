import asyncio
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
from trinity.config import (
    ChainConfig,
)


class LightNode(Node):
    chain_class: Type[LightDispatchChain] = None

    _chain: LightDispatchChain = None
    _p2p_server: LightPeerChain = None

    network_id: int = None
    nodekey: PrivateKey = None

    def __init__(self, chain_config: ChainConfig) -> None:
        super().__init__(chain_config)

        self.network_id = chain_config.network_id
        self.nodekey = chain_config.nodekey

        self._port = chain_config.port
        self._discovery = DiscoveryProtocol(
            chain_config.nodekey,
            Address('0.0.0.0', chain_config.port, chain_config.port),
            bootstrap_nodes=chain_config.bootstrap_nodes,
        )
        self._peer_pool = self._create_peer_pool(chain_config)
        self.add_service(self._peer_pool)

    async def _run(self):
        # TODO add a datagram endpoint service that can be added with self.add_service
        self.logger.info(
            "enode://%s@%s:%s",
            self.nodekey.public_key.to_hex()[2:],
            '0.0.0.0',
            self._port,
        )
        self.logger.info('network: %s', self.network_id)
        transport, _ = await asyncio.get_event_loop().create_datagram_endpoint(
            lambda: self._discovery,
            local_addr=('0.0.0.0', self._port)
        )
        await self._discovery.bootstrap()
        try:
            await super()._run()
        finally:
            await self._discovery.stop()

    def get_chain(self) -> LightDispatchChain:
        if self._chain is None:
            if self.chain_class is None:
                raise AttributeError("LightNode subclass must set chain_class")
            self._chain = self.chain_class(self._headerdb, peer_chain=self.get_p2p_server())

        return self._chain

    def get_p2p_server(self) -> LightPeerChain:
        if self._p2p_server is None:
            self._p2p_server = LightPeerChain(self.headerdb, self._peer_pool)
        return self._p2p_server

    def _create_peer_pool(self, chain_config: ChainConfig) -> PeerPool:
        return PreferredNodePeerPool(
            LESPeer,
            self.headerdb,
            chain_config.network_id,
            chain_config.nodekey,
            self._discovery,
            preferred_nodes=chain_config.preferred_nodes,
        )
