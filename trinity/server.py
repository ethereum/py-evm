from abc import abstractmethod
import asyncio
from typing import (
    cast,
    Generic,
    Sequence,
    Tuple,
    Type,
    TypeVar,
)
from lahja import EndpointAPI

from eth_keys import datatypes
from cancel_token import CancelToken, OperationCancelled
from eth_typing import BlockNumber

from eth.abc import AtomicDatabaseAPI, VirtualMachineAPI

from eth2.beacon.chains.base import BeaconChain

from p2p.abc import NodeAPI
from p2p.constants import DEFAULT_MAX_PEERS, DEVP2P_V5
from p2p.disconnect import DisconnectReason
from p2p.exceptions import (
    HandshakeFailure,
    PeerConnectionLost,
)
from p2p.handshake import DevP2PHandshakeParams
from p2p.peer import receive_handshake
from p2p.service import BaseService

from trinity._utils.version import construct_trinity_client_identifier
from trinity.chains.base import AsyncChainAPI
from trinity.constants import DEFAULT_PREFERRED_NODES
from trinity.db.eth1.chain import BaseAsyncChainDB
from trinity.db.eth1.header import BaseAsyncHeaderDB
from trinity.protocol.common.context import ChainContext
from trinity.protocol.common.peer import BasePeerPool
from trinity.protocol.bcc.context import BeaconContext
from trinity.protocol.bcc.peer import BCCPeerPool
from trinity.protocol.bcc.servers import BCCReceiveServer
from trinity.protocol.eth.peer import ETHPeerPool
from trinity.protocol.les.peer import LESPeerPool

DIAL_IN_OUT_RATIO = 0.75
BOUND_IP = '0.0.0.0'

TPeerPool = TypeVar('TPeerPool', bound=BasePeerPool)
T_VM_CONFIGURATION = Tuple[Tuple[BlockNumber, Type[VirtualMachineAPI]], ...]


class BaseServer(BaseService, Generic[TPeerPool]):
    """Server listening for incoming connections"""
    _tcp_listener = None
    peer_pool: TPeerPool

    def __init__(self,
                 privkey: datatypes.PrivateKey,
                 port: int,
                 chain: AsyncChainAPI,
                 chaindb: BaseAsyncChainDB,
                 headerdb: BaseAsyncHeaderDB,
                 base_db: AtomicDatabaseAPI,
                 network_id: int,
                 max_peers: int = DEFAULT_MAX_PEERS,
                 bootstrap_nodes: Sequence[NodeAPI] = None,
                 preferred_nodes: Sequence[NodeAPI] = None,
                 event_bus: EndpointAPI = None,
                 token: CancelToken = None,
                 ) -> None:
        super().__init__(token)
        # cross process event bus
        self.event_bus = event_bus

        # setup parameters for the base devp2p handshake.
        self.p2p_handshake_params = DevP2PHandshakeParams(
            client_version_string=construct_trinity_client_identifier(),
            listen_port=port,
            version=DEVP2P_V5,
        )

        # chain information
        self.chain = chain
        self.chaindb = chaindb
        self.headerdb = headerdb
        self.base_db = base_db

        # node information
        self.privkey = privkey
        self.port = port
        self.network_id = network_id
        self.max_peers = max_peers
        self.bootstrap_nodes = bootstrap_nodes
        self.preferred_nodes = preferred_nodes
        if self.preferred_nodes is None and network_id in DEFAULT_PREFERRED_NODES:
            self.preferred_nodes = DEFAULT_PREFERRED_NODES[self.network_id]

        # child services
        self.peer_pool = self._make_peer_pool()

        if not bootstrap_nodes:
            self.logger.warning("Running with no bootstrap nodes")

    @abstractmethod
    def _make_peer_pool(self) -> TPeerPool:
        ...

    async def _start_tcp_listener(self) -> None:
        # TODO: Support IPv6 addresses as well.
        self._tcp_listener = await asyncio.start_server(
            self.receive_handshake,
            host=BOUND_IP,
            port=self.port,
        )

    async def _close_tcp_listener(self) -> None:
        if self._tcp_listener:
            self._tcp_listener.close()
            await self._tcp_listener.wait_closed()

    async def _run(self) -> None:
        self.logger.info("Running server...")
        await self._start_tcp_listener()
        self.logger.info(
            "enode://%s@%s:%s",
            self.privkey.public_key.to_hex()[2:],
            BOUND_IP,
            self.port,
        )
        self.logger.info('network: %s', self.network_id)
        self.logger.info('peers: max_peers=%s', self.max_peers)

        self.run_daemon(self.peer_pool)

        await self.cancel_token.wait()

    async def _cleanup(self) -> None:
        self.logger.info("Closing server...")
        await self._close_tcp_listener()

    async def receive_handshake(
            self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        expected_exceptions = (
            TimeoutError,
            PeerConnectionLost,
            HandshakeFailure,
            asyncio.IncompleteReadError,
        )

        def _cleanup_reader_and_writer() -> None:
            if not reader.at_eof():
                reader.feed_eof()
            writer.close()

        try:
            await self._receive_handshake(reader, writer)
        except expected_exceptions as e:
            self.logger.debug("Could not complete handshake: %s", e)
            _cleanup_reader_and_writer()
        except OperationCancelled:
            pass
        except Exception as e:
            self.logger.exception("Unexpected error handling handshake")
            _cleanup_reader_and_writer()

    async def _receive_handshake(
            self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        factory = self.peer_pool.get_peer_factory()
        handshakers = await factory.get_handshakers()
        connection = await receive_handshake(
            reader=reader,
            writer=writer,
            private_key=self.privkey,
            p2p_handshake_params=self.p2p_handshake_params,
            protocol_handshakers=handshakers,
            token=self.cancel_token,
        )

        # Create and register peer in peer_pool
        peer = factory.create_peer(connection)

        if self.peer_pool.is_full:
            await peer.disconnect(DisconnectReason.too_many_peers)
            return
        elif not self.peer_pool.is_valid_connection_candidate(peer.remote):
            await peer.disconnect(DisconnectReason.useless_peer)
            return

        total_peers = len(self.peer_pool)
        inbound_peer_count = len(tuple(
            peer
            for peer
            in self.peer_pool.connected_nodes.values()
            if peer.inbound
        ))
        if total_peers > 1 and inbound_peer_count / total_peers > DIAL_IN_OUT_RATIO:
            # make sure to have at least 1/4 outbound connections
            await peer.disconnect(DisconnectReason.too_many_peers)
            return

        await self.peer_pool.start_peer(peer)


class FullServer(BaseServer[ETHPeerPool]):

    def _make_peer_pool(self) -> ETHPeerPool:
        context = ChainContext(
            headerdb=self.headerdb,
            network_id=self.network_id,
            vm_configuration=self.chain.vm_configuration,
            client_version_string=self.p2p_handshake_params.client_version_string,
            listen_port=self.p2p_handshake_params.listen_port,
            p2p_version=self.p2p_handshake_params.version,
        )
        return ETHPeerPool(
            privkey=self.privkey,
            max_peers=self.max_peers,
            context=context,
            token=self.cancel_token,
            event_bus=self.event_bus
        )


class LightServer(BaseServer[LESPeerPool]):

    def _make_peer_pool(self) -> LESPeerPool:
        context = ChainContext(
            headerdb=self.headerdb,
            network_id=self.network_id,
            vm_configuration=self.chain.vm_configuration,
            client_version_string=self.p2p_handshake_params.client_version_string,
            listen_port=self.p2p_handshake_params.listen_port,
            p2p_version=self.p2p_handshake_params.version,
        )
        return LESPeerPool(
            privkey=self.privkey,
            max_peers=self.max_peers,
            context=context,
            token=self.cancel_token,
            event_bus=self.event_bus
        )


class BCCServer(BaseServer[BCCPeerPool]):

    def __init__(self,
                 privkey: datatypes.PrivateKey,
                 port: int,
                 chain: AsyncChainAPI,
                 chaindb: BaseAsyncChainDB,
                 headerdb: BaseAsyncHeaderDB,
                 base_db: AtomicDatabaseAPI,
                 network_id: int,
                 max_peers: int = DEFAULT_MAX_PEERS,
                 bootstrap_nodes: Sequence[NodeAPI] = None,
                 preferred_nodes: Sequence[NodeAPI] = None,
                 event_bus: EndpointAPI = None,
                 token: CancelToken = None,
                 ) -> None:
        super().__init__(
            privkey,
            port,
            chain,
            chaindb,
            headerdb,
            base_db,
            network_id,
            max_peers,
            bootstrap_nodes,
            preferred_nodes,
            event_bus,
            token,
        )
        self.receive_server = self._make_receive_server()

    async def _run(self) -> None:
        self.logger.info("Running server...")
        await self._start_tcp_listener()
        self.logger.info(
            "enode://%s@%s:%s",
            self.privkey.public_key.to_hex()[2:],
            BOUND_IP,
            self.port,
        )
        self.logger.info('network: %s', self.network_id)
        self.logger.info('peers: max_peers=%s', self.max_peers)

        self.run_daemon(self.peer_pool)
        self.run_daemon(self.receive_server)

        await self.cancel_token.wait()

    def _make_peer_pool(self) -> BCCPeerPool:
        context = BeaconContext(
            chain_db=self.chaindb,
            network_id=self.network_id,
            client_version_string=self.p2p_handshake_params.client_version_string,
            listen_port=self.p2p_handshake_params.listen_port,
            p2p_version=self.p2p_handshake_params.version,
        )
        return BCCPeerPool(
            privkey=self.privkey,
            max_peers=self.max_peers,
            context=context,
            token=self.cancel_token,
            event_bus=self.event_bus
        )

    def _make_receive_server(self) -> BCCReceiveServer:
        return BCCReceiveServer(
            chain=cast(BeaconChain, self.chain),
            peer_pool=self.peer_pool,
            token=self.cancel_token,
        )
