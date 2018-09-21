from abc import abstractmethod
import asyncio
import logging
import secrets
from typing import (
    cast,
    Sequence,
    Tuple,
    Union,
)

from eth_keys import datatypes

from eth_utils import big_endian_to_int

from cancel_token import CancelToken, OperationCancelled

from lahja import (
    Endpoint
)

from eth.chains import AsyncChain

from eth_typing import BlockNumber

from eth.constants import GENESIS_BLOCK_NUMBER

from p2p.auth import (
    decode_authentication,
    HandshakeResponder,
)
from p2p.constants import (
    ENCRYPTED_AUTH_MSG_LEN,
    DEFAULT_MAX_PEERS,
    HASH_LEN,
    REPLY_TIMEOUT,
)
from p2p.discovery import (
    get_v5_topic,
    DiscoveryByTopicProtocol,
    DiscoveryProtocol,
    DiscoveryService,
    PreferredNodeDiscoveryProtocol,
)
from p2p.exceptions import (
    DecryptionError,
    HandshakeFailure,
    PeerConnectionLost,
)
from p2p.kademlia import (
    Address,
    Node,
)
from p2p.nat import UPnPService
from p2p.p2p_proto import (
    DisconnectReason,
)
from p2p.peer import BasePeer, PeerConnection
from p2p.service import BaseService

from trinity.db.base import AsyncBaseDB
from trinity.db.chain import AsyncChainDB
from trinity.db.header import AsyncHeaderDB
from trinity.protocol.common.constants import DEFAULT_PREFERRED_NODES
from trinity.protocol.common.context import ChainContext
from trinity.protocol.eth.peer import ETHPeerPool
from trinity.protocol.les.peer import LESPeerPool
from trinity.sync.full.service import FullNodeSyncer
from trinity.sync.light.chain import LightChainSyncer


DIAL_IN_OUT_RATIO = 0.75


ANY_PEER_POOL = Union[ETHPeerPool, LESPeerPool]


class BaseServer(BaseService):
    """Server listening for incoming connections"""
    _tcp_listener = None
    peer_pool: ANY_PEER_POOL

    def __init__(self,
                 privkey: datatypes.PrivateKey,
                 port: int,
                 chain: AsyncChain,
                 chaindb: AsyncChainDB,
                 headerdb: AsyncHeaderDB,
                 base_db: AsyncBaseDB,
                 network_id: int,
                 max_peers: int = DEFAULT_MAX_PEERS,
                 bootstrap_nodes: Tuple[Node, ...] = None,
                 preferred_nodes: Sequence[Node] = None,
                 use_discv5: bool = False,
                 event_bus: Endpoint = None,
                 token: CancelToken = None,
                 ) -> None:
        super().__init__(token)
        self.event_bus = event_bus
        self.headerdb = headerdb
        self.chaindb = chaindb
        self.chain = chain
        self.base_db = base_db
        self.privkey = privkey
        self.port = port
        self.network_id = network_id
        self.max_peers = max_peers
        self.bootstrap_nodes = bootstrap_nodes
        self.preferred_nodes = preferred_nodes
        if self.preferred_nodes is None and network_id in DEFAULT_PREFERRED_NODES:
            self.preferred_nodes = DEFAULT_PREFERRED_NODES[self.network_id]
        self.use_discv5 = use_discv5
        self.upnp_service = UPnPService(port, token=self.cancel_token)
        self.peer_pool = self._make_peer_pool()

        if not bootstrap_nodes:
            self.logger.warning("Running with no bootstrap nodes")

    @abstractmethod
    def _make_peer_pool(self) -> ANY_PEER_POOL:
        pass

    @abstractmethod
    def _make_syncer(self) -> BaseService:
        pass

    async def _start_tcp_listener(self) -> None:
        # TODO: Support IPv6 addresses as well.
        self._tcp_listener = await asyncio.start_server(
            self.receive_handshake,
            host='0.0.0.0',
            port=self.port,
        )

    async def _close_tcp_listener(self) -> None:
        if self._tcp_listener:
            self._tcp_listener.close()
            await self._tcp_listener.wait_closed()

    async def _run(self) -> None:
        self.logger.info("Running server...")
        mapped_external_ip = await self.upnp_service.add_nat_portmap()
        if mapped_external_ip is None:
            external_ip = '0.0.0.0'
        else:
            external_ip = mapped_external_ip
        await self._start_tcp_listener()
        self.logger.info(
            "enode://%s@%s:%s",
            self.privkey.public_key.to_hex()[2:],
            external_ip,
            self.port,
        )
        self.logger.info('network: %s', self.network_id)
        self.logger.info('peers: max_peers=%s', self.max_peers)
        addr = Address(external_ip, self.port, self.port)
        if self.use_discv5:
            topic = self._get_discv5_topic()
            self.logger.info(
                "Using experimental v5 (topic) discovery mechanism; topic: %s", topic)
            discovery_proto: DiscoveryProtocol = DiscoveryByTopicProtocol(
                topic, self.privkey, addr, self.bootstrap_nodes, self.cancel_token)
        else:
            discovery_proto = PreferredNodeDiscoveryProtocol(
                self.privkey, addr, self.bootstrap_nodes, self.preferred_nodes, self.cancel_token)
        self.discovery = DiscoveryService(
            discovery_proto,
            self.peer_pool,
            self.port,
            token=self.cancel_token,
        )
        self.run_daemon(self.peer_pool)
        self.run_daemon(self.discovery)
        # UPNP service is still experimental and not essential, so we don't use run_daemon() for
        # it as that means if it crashes we'd be terminated as well.
        self.run_child_service(self.upnp_service)
        self.syncer = self._make_syncer()
        await self.syncer.run()

    async def _cleanup(self) -> None:
        self.logger.info("Closing server...")
        await self._close_tcp_listener()

    def _get_discv5_topic(self) -> bytes:
        genesis_hash = self.headerdb.get_canonical_block_hash(BlockNumber(GENESIS_BLOCK_NUMBER))
        # For now DiscoveryByTopicProtocol supports a single topic, so we use the latest version
        # of our supported protocols.
        proto = self.peer_pool.peer_factory_class.peer_class._supported_sub_protocols[-1]
        return get_v5_topic(proto, genesis_hash)

    async def receive_handshake(
            self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        expected_exceptions = (
            TimeoutError,
            PeerConnectionLost,
            HandshakeFailure,
            asyncio.IncompleteReadError,
        )
        try:
            await self._receive_handshake(reader, writer)
        except expected_exceptions as e:
            self.logger.debug("Could not complete handshake: %s", e)
        except OperationCancelled:
            pass
        except Exception as e:
            self.logger.exception("Unexpected error handling handshake")

    async def _receive_handshake(
            self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        msg = await self.wait(
            reader.read(ENCRYPTED_AUTH_MSG_LEN),
            timeout=REPLY_TIMEOUT)

        ip, socket, *_ = writer.get_extra_info("peername")
        remote_address = Address(ip, socket)
        self.logger.debug("Receiving handshake from %s", remote_address)
        got_eip8 = False
        try:
            ephem_pubkey, initiator_nonce, initiator_pubkey = decode_authentication(
                msg, self.privkey)
        except DecryptionError:
            # Try to decode as EIP8
            got_eip8 = True
            msg_size = big_endian_to_int(msg[:2])
            remaining_bytes = msg_size - ENCRYPTED_AUTH_MSG_LEN + 2
            msg += await self.wait(
                reader.read(remaining_bytes),
                timeout=REPLY_TIMEOUT)
            try:
                ephem_pubkey, initiator_nonce, initiator_pubkey = decode_authentication(
                    msg, self.privkey)
            except DecryptionError as e:
                self.logger.debug("Failed to decrypt handshake: %s", e)
                return

        initiator_remote = Node(initiator_pubkey, remote_address)
        responder = HandshakeResponder(initiator_remote, self.privkey, got_eip8, self.cancel_token)

        responder_nonce = secrets.token_bytes(HASH_LEN)
        auth_ack_msg = responder.create_auth_ack_message(responder_nonce)
        auth_ack_ciphertext = responder.encrypt_auth_ack_message(auth_ack_msg)

        # Use the `writer` to send the reply to the remote
        writer.write(auth_ack_ciphertext)
        await self.wait(writer.drain())

        # Call `HandshakeResponder.derive_shared_secrets()` and use return values to create `Peer`
        aes_secret, mac_secret, egress_mac, ingress_mac = responder.derive_secrets(
            initiator_nonce=initiator_nonce,
            responder_nonce=responder_nonce,
            remote_ephemeral_pubkey=ephem_pubkey,
            auth_init_ciphertext=msg,
            auth_ack_ciphertext=auth_ack_ciphertext
        )
        connection = PeerConnection(
            reader=reader,
            writer=writer,
            aes_secret=aes_secret,
            mac_secret=mac_secret,
            egress_mac=egress_mac,
            ingress_mac=ingress_mac,
        )

        # Create and register peer in peer_pool
        peer = self.peer_pool.get_peer_factory().create_peer(
            remote=initiator_remote,
            connection=connection,
            inbound=True,
        )

        if self.peer_pool.is_full:
            await peer.disconnect(DisconnectReason.too_many_peers)
            return
        elif not self.peer_pool.is_valid_connection_candidate(peer.remote):
            await peer.disconnect(DisconnectReason.useless_peer)
            return

        total_peers = len(self.peer_pool)
        inbound_peer_count = len([
            peer
            for peer
            in self.peer_pool.connected_nodes.values()
            if peer.inbound
        ])
        if total_peers > 1 and inbound_peer_count / total_peers > DIAL_IN_OUT_RATIO:
            # make sure to have at least 1/4 outbound connections
            await peer.disconnect(DisconnectReason.too_many_peers)
        else:
            # We use self.wait() here as a workaround for
            # https://github.com/ethereum/py-evm/issues/670.
            await self.wait(self.do_handshake(peer))

    async def do_handshake(self, peer: BasePeer) -> None:
        await peer.do_p2p_handshake()
        await peer.do_sub_proto_handshake()
        await self.peer_pool.start_peer(peer)


class FullServer(BaseServer):
    def _make_peer_pool(self) -> ETHPeerPool:
        context = ChainContext(
            headerdb=self.headerdb,
            network_id=self.network_id,
            vm_configuration=self.chain.get_vm_configuration(),
        )
        return ETHPeerPool(
            privkey=self.privkey,
            max_peers=self.max_peers,
            context=context,
            token=self.cancel_token,
            event_bus=self.event_bus
        )

    def _make_syncer(self) -> FullNodeSyncer:
        return FullNodeSyncer(
            self.chain,
            self.chaindb,
            self.base_db,
            cast(ETHPeerPool, self.peer_pool),
            token=self.cancel_token,
        )


class LightServer(BaseServer):
    def _make_peer_pool(self) -> LESPeerPool:
        context = ChainContext(
            headerdb=self.headerdb,
            network_id=self.network_id,
            vm_configuration=self.chain.get_vm_configuration(),
        )
        return LESPeerPool(
            privkey=self.privkey,
            max_peers=self.max_peers,
            context=context,
            token=self.cancel_token,
            event_bus=self.event_bus
        )

    def _make_syncer(self) -> LightChainSyncer:
        return LightChainSyncer(
            self.chain,
            self.headerdb,
            cast(LESPeerPool, self.peer_pool),
            self.cancel_token,
        )


def _test() -> None:
    import argparse
    from pathlib import Path
    import signal

    from eth.chains.ropsten import RopstenChain, ROPSTEN_GENESIS_HEADER

    from p2p import ecies
    from p2p.constants import ROPSTEN_BOOTNODES

    from trinity.utils.chains import load_nodekey

    from tests.trinity.core.integration_test_helpers import (
        FakeAsyncLevelDB, FakeAsyncHeaderDB, FakeAsyncChainDB, FakeAsyncRopstenChain)

    parser = argparse.ArgumentParser()
    parser.add_argument('-db', type=str, required=True)
    parser.add_argument('-debug', action="store_true")
    parser.add_argument('-bootnodes', type=str, default=[])
    parser.add_argument('-nodekey', type=str)

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s', datefmt='%H:%M:%S')
    log_level = logging.INFO
    if args.debug:
        log_level = logging.DEBUG

    loop = asyncio.get_event_loop()
    db = FakeAsyncLevelDB(args.db)
    headerdb = FakeAsyncHeaderDB(db)
    chaindb = FakeAsyncChainDB(db)
    chaindb.persist_header(ROPSTEN_GENESIS_HEADER)
    chain = FakeAsyncRopstenChain(db)

    # NOTE: Since we may create a different priv/pub key pair every time we run this, remote nodes
    # may try to establish a connection using the pubkey from one of our previous runs, which will
    # result in lots of DecryptionErrors in receive_handshake().
    if args.nodekey:
        privkey = load_nodekey(Path(args.nodekey))
    else:
        privkey = ecies.generate_privkey()

    port = 30303
    if args.bootnodes:
        bootstrap_nodes = args.bootnodes.split(',')
    else:
        bootstrap_nodes = ROPSTEN_BOOTNODES
    bootstrap_nodes = [Node.from_uri(enode) for enode in bootstrap_nodes]

    server = FullServer(
        privkey,
        port,
        chain,
        chaindb,
        headerdb,
        db,
        RopstenChain.network_id,
        bootstrap_nodes=bootstrap_nodes,
    )
    server.logger.setLevel(log_level)

    sigint_received = asyncio.Event()
    for sig in [signal.SIGINT, signal.SIGTERM]:
        loop.add_signal_handler(sig, sigint_received.set)

    async def exit_on_sigint() -> None:
        await sigint_received.wait()
        await server.cancel()
        loop.stop()

    loop.set_debug(True)
    asyncio.ensure_future(exit_on_sigint())
    asyncio.ensure_future(server.run())
    loop.run_forever()
    loop.close()


if __name__ == "__main__":
    _test()
