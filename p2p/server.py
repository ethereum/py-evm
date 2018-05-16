import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
import secrets
from typing import (
    List,
    Type,
    TYPE_CHECKING,
)

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
    CancelToken,
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
    _server = None

    def __init__(self,
                 privkey: datatypes.PrivateKey,
                 address: Address,
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
        super().__init__(CancelToken('Server'))
        self.headerdb = headerdb
        self.privkey = privkey
        self.address = address
        self.network_id = network_id
        self.peer_class = peer_class
        if not bootstrap_nodes:
            if self.network_id == MAINNET_NETWORK_ID:
                bootstrap_nodes = MAINNET_BOOTNODES
            elif self.network_id == ROPSTEN_NETWORK_ID:
                bootstrap_nodes = ROPSTEN_BOOTNODES
            else:
                self.logger.warn("No bootstrap nodes for network id: {}".format(network_id))
                bootstrap_nodes = []
        self.discovery = DiscoveryProtocol(
            self.privkey, self.address, bootstrap_nodes=bootstrap_nodes)
        self.peer_pool = peer_pool_class(
            peer_class,
            self.headerdb,
            self.network_id,
            self.privkey,
            self.discovery,
            min_peers=min_peers,
        )
        self.syncer = FullNodeSyncer(chain, chaindb, base_db, self.peer_pool, self.cancel_token)

    async def refresh_nat_portmap(self) -> None:
        """Run an infinite loop refreshing our NAT port mapping.

        On every iteration we configure the port mapping with a lifetime of 30 minutes and then
        sleep for that long as well.
        """
        lifetime = 30 * 60
        while not self.is_finished:
            self.logger.info("Setting up NAT portmap...")
            # This is experimental and it's OK if it fails, hence the bare except.
            try:
                await self._add_nat_portmap(lifetime)
            except Exception as e:
                if (isinstance(e, upnpclient.soap.SOAPError) and
                        e.args == (718, 'ConflictInMappingEntry')):
                    # An entry already exists with the parameters we specified. Maybe the router
                    # didn't clean it up after it expired or it has been configured by other piece
                    # of software, either way we should not override it.
                    # https://tools.ietf.org/id/draft-ietf-pcp-upnp-igd-interworking-07.html#errors
                    self.logger.info("NAT port mapping already configured, not overriding it")
                else:
                    self.logger.exception("Failed to setup NAT portmap")

            try:
                await wait_with_token(asyncio.sleep(lifetime), token=self.cancel_token)
            except OperationCancelled:
                break

    async def _add_nat_portmap(self, lifetime: int) -> None:
        loop = asyncio.get_event_loop()
        # Use loop.run_in_executor() because upnpclient.discover() is blocking and may take a
        # while to complete. We must use a ThreadPoolExecutor() because the
        # response from upnpclient.discover() can't be pickled.
        devices = await wait_with_token(
            loop.run_in_executor(ThreadPoolExecutor(max_workers=1), upnpclient.discover),
            token=self.cancel_token,
            timeout=2 * REPLY_TIMEOUT)

        # If there are no UPNP devices we can exit early
        if not devices:
            self.logger.info("No UPNP-enabled devices found")
            return

        # Now we loop over all of the devices attempting to setup a port
        # mapping from their external IP to the internal IP.
        for device in devices:
            try:
                connection = device.WANIPConn1
            except AttributeError:
                continue

            # Detect our internal IP address (or abort if we can't determine
            # the internal IP address
            for iface in netifaces.interfaces():
                for _, addr in netifaces.ifaddresses(iface):
                    network = addr['addr'].rstrip('.', 1)
                    if network in device.location:
                        internal_ip = addr['addr']
                        break
            else:
                self.logger.warn(
                    "Unable to detect internal IP address in order to setup NAT portmap"
                )
                continue

            connection.AddPortMapping(
                NewRemoteHost=connection.GetExternalIPAddress()['NewExternalIPAddress'],
                NewExternalPort=self.server_address.tcp_port,
                NewProtocol='TCP',
                NewInternalPort=self.server_address.tcp_port,
                NewInternalClient=internal_ip,
                NewEnabled='1',
                NewPortMappingDescription='Created by Py-EVM',
                NewLeaseDuration=lifetime,
            )
            self.logger.info("NAT port forwarding successfully setup")
            break
        else:
            self.logger.warning('Unable to setup port forwarding for NAT')

    async def _start(self) -> None:
        self._server = await asyncio.start_server(
            self.receive_handshake,
            host=self.address.ip,
            port=self.address.tcp_port,
        )

    async def _close(self) -> None:
        self._server.close()
        await self._server.wait_closed()

    async def _run(self) -> None:
        self.logger.info("Running server...")
        await self._start()
        self.logger.info(
            "enode://%s@%s:%s",
            self.privkey.public_key.to_hex()[2:],
            self.address.ip,
            self.address.tcp_port,
        )
        await self.discovery.create_endpoint()
        asyncio.ensure_future(self.refresh_nat_portmap())
        asyncio.ensure_future(self.discovery.bootstrap())
        asyncio.ensure_future(self.peer_pool.run())
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
    parser.add_argument('-address', type=str, required=True)
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
    chain = FakeAsyncRopstenChain(chaindb)

    # NOTE: Since we may create a different priv/pub key pair every time we run this, remote nodes
    # may try to establish a connection using the pubkey from one of our previous runs, which will
    # result in lots of DecryptionErrors in receive_handshake().
    if args.nodekey:
        privkey = load_nodekey(args.nodekey)
    else:
        privkey = ecies.generate_privkey()

    ip, port = args.address.split(':')
    address = Address(ip, int(port))
    if args.bootnodes:
        bootstrap_nodes = args.bootnodes.split(',')
    else:
        bootstrap_nodes = []

    server = Server(
        privkey,
        address,
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
