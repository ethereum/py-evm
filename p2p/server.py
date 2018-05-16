import asyncio
from concurrent.futures import ThreadPoolExecutor
import ipaddress
import logging
import secrets
import socket
from typing import (
    cast,
    List,
    Type,
    TYPE_CHECKING,
)
from urllib.parse import urlparse

import netifaces
import upnpclient

from eth_keys import datatypes

from eth_utils import big_endian_to_int

from evm.chains import AsyncChain
from evm.chains.mainnet import (
    MAINNET_NETWORK_ID,
)
from evm.chains.ropsten import (
    ROPSTEN_NETWORK_ID,
)
from evm.db.backends.base import BaseDB
from evm.db.chain import AsyncChainDB

from p2p.auth import (
    decode_authentication,
    HandshakeResponder,
)
from p2p.cancel_token import (
    wait_with_token,
)
from p2p.constants import (
    ENCRYPTED_AUTH_MSG_LEN,
    DEFAULT_MIN_PEERS,
    HASH_LEN,
    MAINNET_BOOTNODES,
    REPLY_TIMEOUT,
    ROPSTEN_BOOTNODES,
)
from p2p.discovery import DiscoveryProtocol
from p2p.exceptions import (
    DecryptionError,
    HandshakeFailure,
    OperationCancelled,
    PeerConnectionLost,
)
from p2p.kademlia import (
    Address,
    Node,
)
from p2p.peer import (
    BasePeer,
    ETHPeer,
    PeerPool,
)
from p2p.service import BaseService
from p2p.sync import FullNodeSyncer

if TYPE_CHECKING:
    from trinity.db.header import BaseAsyncHeaderDB  # noqa: F401


class Server(BaseService):
    """Server listening for incoming connections"""
    logger = logging.getLogger("p2p.server.Server")
    _tcp_listener = None
    _udp_listener = None
    _nat_portmap_lifetime = 30 * 60

    def __init__(self,
                 privkey: datatypes.PrivateKey,
                 port: int,
                 chain: AsyncChain,
                 chaindb: AsyncChainDB,
                 headerdb: 'BaseAsyncHeaderDB',
                 base_db: BaseDB,
                 network_id: int,
                 min_peers: int = DEFAULT_MIN_PEERS,
                 peer_class: Type[BasePeer] = ETHPeer,
                 peer_pool_class: Type[PeerPool] = PeerPool,
                 bootstrap_nodes: List[str] = [],
                 ) -> None:
        super().__init__()
        self.headerdb = headerdb
        self.chaindb = chaindb
        self.chain = chain
        self.base_db = base_db
        self.privkey = privkey
        self.port = port
        self.network_id = network_id
        self.peer_class = peer_class
        self.peer_pool_class = peer_pool_class
        self.min_peers = min_peers
        if not bootstrap_nodes:
            if self.network_id == MAINNET_NETWORK_ID:
                self.bootstrap_nodes = MAINNET_BOOTNODES
            elif self.network_id == ROPSTEN_NETWORK_ID:
                self.bootstrap_nodes = ROPSTEN_BOOTNODES
            else:
                self.logger.warn("No bootstrap nodes for network id: {}".format(network_id))
                self.bootstrap_nodes = []

    async def refresh_nat_portmap(self) -> None:
        """Run an infinite loop refreshing our NAT port mapping.

        On every iteration we configure the port mapping with a lifetime of 30 minutes and then
        sleep for that long as well.
        """
        while not self.is_finished:
            try:
                # We start with a sleep because our _run() method will setup the initial portmap.
                await wait_with_token(
                    asyncio.sleep(self._nat_portmap_lifetime), token=self.cancel_token)
                await self.add_nat_portmap()
            except OperationCancelled:
                break

    async def add_nat_portmap(self) -> None:
        self.logger.info("Setting up NAT portmap...")
        # This is experimental and it's OK if it fails, hence the bare except.
        try:
            upnp_dev = await self._discover_upnp_device()
            if upnp_dev is None:
                return
            await self._add_nat_portmap(upnp_dev)
        except upnpclient.soap.SOAPError as e:
            if e.args == (718, 'ConflictInMappingEntry'):
                # An entry already exists with the parameters we specified. Maybe the router
                # didn't clean it up after it expired or it has been configured by other piece
                # of software, either way we should not override it.
                # https://tools.ietf.org/id/draft-ietf-pcp-upnp-igd-interworking-07.html#errors
                self.logger.info("NAT port mapping already configured, not overriding it")
            else:
                self.logger.exception("Failed to setup NAT portmap")
        except Exception:
            self.logger.exception("Failed to setup NAT portmap")

    def _find_internal_ip_on_device_network(self, upnp_dev: upnpclient.upnp.Device) -> str:
        parsed_url = urlparse(upnp_dev.location)
        # Get an ipaddress.IPv4Network instance for the upnp device's network.
        upnp_dev_net = ipaddress.ip_network(parsed_url.hostname + '/24', strict=False)
        for iface in netifaces.interfaces():
            for family, addresses in netifaces.ifaddresses(iface).items():
                # TODO: Support IPv6 addresses as well.
                if family != netifaces.AF_INET:
                    continue
                for item in addresses:
                    if ipaddress.ip_address(item['addr']) in upnp_dev_net:
                        return item['addr']
        return None

    async def _add_nat_portmap(self, upnp_dev: upnpclient.upnp.Device) -> None:
        # Detect our internal IP address (or abort if we can't determine
        # the internal IP address
        internal_ip = self._find_internal_ip_on_device_network(upnp_dev)
        if internal_ip is None:
            self.logger.warn(
                "Unable to detect internal IP address in order to setup NAT portmap"
            )
            return

        external_ip = upnp_dev.WANIPConn1.GetExternalIPAddress()['NewExternalIPAddress']
        for protocol, description in [('TCP', 'ethereum p2p'), ('UDP', 'ethereum discovery')]:
            upnp_dev.WANIPConn1.AddPortMapping(
                NewRemoteHost=external_ip,
                NewExternalPort=self.port,
                NewProtocol=protocol,
                NewInternalPort=self.port,
                NewInternalClient=internal_ip,
                NewEnabled='1',
                NewPortMappingDescription=description,
                NewLeaseDuration=self._nat_portmap_lifetime,
            )
        self.logger.info("NAT port forwarding successfully setup")

    async def _discover_upnp_device(self) -> upnpclient.upnp.Device:
        loop = asyncio.get_event_loop()
        # UPnP discovery can take a long time, so use a loooong timeout here.
        discover_timeout = 10 * REPLY_TIMEOUT
        # Use loop.run_in_executor() because upnpclient.discover() is blocking and may take a
        # while to complete. We must use a ThreadPoolExecutor() because the
        # response from upnpclient.discover() can't be pickled.
        devices = await wait_with_token(
            loop.run_in_executor(ThreadPoolExecutor(max_workers=1), upnpclient.discover),
            token=self.cancel_token,
            timeout=discover_timeout)

        # If there are no UPNP devices we can exit early
        if not devices:
            self.logger.info("No UPNP-enabled devices found")
            return None

        # Now we loop over all of the devices until we find one that we can use.
        for device in devices:
            try:
                device.WANIPConn1
            except AttributeError:
                continue
            return device
        return None

    async def _start_tcp_listener(self) -> None:
        # TODO: Support IPv6 addresses as well.
        self._tcp_listener = await asyncio.start_server(
            self.receive_handshake,
            host='0.0.0.0',
            port=self.port,
        )

    async def _close_tcp_listener(self) -> None:
        self._tcp_listener.close()
        await self._tcp_listener.wait_closed()

    async def _start_udp_listener(self, discovery: DiscoveryProtocol) -> None:
        loop = asyncio.get_event_loop()
        # TODO: Support IPv6 addresses as well.
        self._udp_transport, _ = await loop.create_datagram_endpoint(
            lambda: discovery,
            local_addr=('0.0.0.0', self.port),
            family=socket.AF_INET)

    async def _close_udp_listener(self) -> None:
        cast(asyncio.DatagramTransport, self._udp_transport).abort()

    async def _close(self) -> None:
        await asyncio.gather(
            self._close_tcp_listener(), self._close_udp_listener())

    def _make_syncer(self, peer_pool: PeerPool) -> BaseService:
        # This method exists only so that ShardSyncer can provide a different implementation.
        return FullNodeSyncer(
            self.chain, self.chaindb, self.base_db, peer_pool, self.cancel_token)

    def _make_peer_pool(self, discovery: DiscoveryProtocol) -> PeerPool:
        # This method exists only so that ShardSyncer can provide a different implementation.
        return self.peer_pool_class(
            self.peer_class,
            self.headerdb,
            self.network_id,
            self.privkey,
            discovery,
            min_peers=self.min_peers,
        )

    async def _run(self) -> None:
        self.logger.info("Running server...")
        upnp_dev = await self._discover_upnp_device()
        external_ip = '0.0.0.0'
        if upnp_dev is not None:
            external_ip = upnp_dev.WANIPConn1.GetExternalIPAddress()['NewExternalIPAddress']
            await self._add_nat_portmap(upnp_dev)
        await self._start_tcp_listener()
        self.logger.info(
            "enode://%s@%s:%s",
            self.privkey.public_key.to_hex()[2:],
            external_ip,
            self.port,
        )
        addr = Address(external_ip, self.port, self.port)
        self.discovery = DiscoveryProtocol(self.privkey, addr, bootstrap_nodes=self.bootstrap_nodes)
        await self._start_udp_listener(self.discovery)
        self.peer_pool = self._make_peer_pool(self.discovery)
        asyncio.ensure_future(self.refresh_nat_portmap())
        asyncio.ensure_future(self.discovery.bootstrap())
        asyncio.ensure_future(self.peer_pool.run())
        self.syncer = self._make_syncer(self.peer_pool)
        await self.syncer.run()

    async def _cleanup(self) -> None:
        self.logger.info("Closing server...")
        await self.peer_pool.cancel()
        await self.discovery.stop()
        await self._close()

    async def receive_handshake(
            self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        expected_exceptions = (
            TimeoutError, PeerConnectionLost, HandshakeFailure, asyncio.IncompleteReadError,
            ConnectionResetError, BrokenPipeError)
        try:
            await self._receive_handshake(reader, writer)
        except expected_exceptions as e:
            self.logger.debug("Could not complete handshake", exc_info=True)
        except OperationCancelled:
            pass
        except Exception as e:
            self.logger.exception("Unexpected error handling handshake")

    async def _receive_handshake(
            self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        msg = await wait_with_token(
            reader.read(ENCRYPTED_AUTH_MSG_LEN),
            token=self.cancel_token,
            timeout=REPLY_TIMEOUT,
        )

        ip, socket, *_ = writer.get_extra_info("peername")
        remote_address = Address(ip, socket)
        self.logger.debug("Receiving handshake from %s", remote_address)
        try:
            ephem_pubkey, initiator_nonce, initiator_pubkey = decode_authentication(
                msg, self.privkey)
        except DecryptionError:
            # Try to decode as EIP8
            msg_size = big_endian_to_int(msg[:2])
            remaining_bytes = msg_size - ENCRYPTED_AUTH_MSG_LEN + 2
            msg += await wait_with_token(
                reader.read(remaining_bytes),
                token=self.cancel_token,
                timeout=REPLY_TIMEOUT,
            )
            try:
                ephem_pubkey, initiator_nonce, initiator_pubkey = decode_authentication(
                    msg, self.privkey)
            except DecryptionError as e:
                self.logger.debug("Failed to decrypt handshake", exc_info=True)
                return

        # Create `HandshakeResponder(remote: kademlia.Node, privkey: datatypes.PrivateKey)` instance
        initiator_remote = Node(initiator_pubkey, remote_address)
        responder = HandshakeResponder(initiator_remote, self.privkey, self.cancel_token)

        # Call `HandshakeResponder.create_auth_ack_message(nonce: bytes)` to create the reply
        responder_nonce = secrets.token_bytes(HASH_LEN)
        auth_ack_msg = responder.create_auth_ack_message(nonce=responder_nonce)
        auth_ack_ciphertext = responder.encrypt_auth_ack_message(auth_ack_msg)

        # Use the `writer` to send the reply to the remote
        writer.write(auth_ack_ciphertext)
        await writer.drain()

        # Call `HandshakeResponder.derive_shared_secrets()` and use return values to create `Peer`
        aes_secret, mac_secret, egress_mac, ingress_mac = responder.derive_secrets(
            initiator_nonce=initiator_nonce,
            responder_nonce=responder_nonce,
            remote_ephemeral_pubkey=ephem_pubkey,
            auth_init_ciphertext=msg,
            auth_ack_ciphertext=auth_ack_ciphertext
        )

        # Create and register peer in peer_pool
        peer = self.peer_class(
            remote=initiator_remote,
            privkey=self.privkey,
            reader=reader,
            writer=writer,
            aes_secret=aes_secret,
            mac_secret=mac_secret,
            egress_mac=egress_mac,
            ingress_mac=ingress_mac,
            headerdb=self.headerdb,
            network_id=self.network_id
        )

        await self.do_handshake(peer)

    async def do_handshake(self, peer: BasePeer) -> None:
        await peer.do_p2p_handshake(),
        await peer.do_sub_proto_handshake()
        self._start_peer(peer)

    def _start_peer(self, peer: BasePeer) -> None:
        # This method exists only so that we can monkey-patch it in tests.
        self.peer_pool.start_peer(peer)


def _test() -> None:
    import argparse
    import signal

    from evm.db.backends.memory import MemoryDB
    from evm.chains.ropsten import RopstenChain, ROPSTEN_GENESIS_HEADER

    from p2p import ecies
    from p2p.peer import ETHPeer

    from trinity.utils.chains import load_nodekey

    from tests.p2p.integration_test_helpers import FakeAsyncHeaderDB
    from tests.p2p.integration_test_helpers import FakeAsyncChainDB, FakeAsyncRopstenChain

    parser = argparse.ArgumentParser()
    parser.add_argument('-debug', action="store_true")
    parser.add_argument('-bootnodes', type=str, default=[])
    parser.add_argument('-nodekey', type=str)

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s', datefmt='%H:%M:%S')
    log_level = logging.INFO
    if args.debug:
        log_level = logging.DEBUG
    logging.getLogger('p2p.server.Server').setLevel(log_level)

    loop = asyncio.get_event_loop()
    db = MemoryDB()
    headerdb = FakeAsyncHeaderDB(db)
    chaindb = FakeAsyncChainDB(db)
    chaindb.persist_header(ROPSTEN_GENESIS_HEADER)
    chain = FakeAsyncRopstenChain(db)

    # NOTE: Since we may create a different priv/pub key pair every time we run this, remote nodes
    # may try to establish a connection using the pubkey from one of our previous runs, which will
    # result in lots of DecryptionErrors in receive_handshake().
    if args.nodekey:
        privkey = load_nodekey(args.nodekey)
    else:
        privkey = ecies.generate_privkey()

    port = 30303
    if args.bootnodes:
        bootstrap_nodes = args.bootnodes.split(',')
    else:
        bootstrap_nodes = []

    server = Server(
        privkey,
        port,
        chain,
        chaindb,
        headerdb,
        db,
        RopstenChain.network_id,
        peer_class=ETHPeer,
        bootstrap_nodes=bootstrap_nodes,
    )

    sigint_received = asyncio.Event()
    for sig in [signal.SIGINT, signal.SIGTERM]:
        loop.add_signal_handler(sig, sigint_received.set)

    async def exit_on_sigint():
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
