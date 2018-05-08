import asyncio
import logging
import secrets

from typing import (
    List,
    Type,
)

import upnpclient

from eth_keys import datatypes

from eth_utils import big_endian_to_int

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
    REPLY_TIMEOUT,
)
from p2p.discovery import DiscoveryProtocol
from p2p.exceptions import (
    DecryptionError,
    HandshakeFailure,
    OperationCancelled,
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


class Server:
    """Server listening for incoming connections"""
    logger = logging.getLogger("p2p.server.Server")
    _server = None

    def __init__(self,
                 privkey: datatypes.PrivateKey,
                 server_address: Address,
                 chaindb: AsyncChainDB,
                 bootstrap_nodes: List[str],
                 network_id: int,
                 min_peers: int = DEFAULT_MIN_PEERS,
                 peer_class: Type[BasePeer] = ETHPeer,
                 ) -> None:
        self.cancel_token = CancelToken('Server')
        self.chaindb = chaindb
        self.privkey = privkey
        self.server_address = server_address
        self.network_id = network_id
        self.peer_class = peer_class
        # TODO: bootstrap_nodes should be looked up by network_id.
        self.discovery = DiscoveryProtocol(
            self.privkey, self.server_address, bootstrap_nodes=bootstrap_nodes)
        self.peer_pool = PeerPool(
            peer_class,
            self.chaindb,
            self.network_id,
            self.privkey,
            self.discovery,
            min_peers=min_peers,
        )

    async def refresh_nat_portmap(self) -> None:
        """Run an infinite loop refreshing our NAT port mapping.

        On every iteration we configure the port mapping with a lifetime of 30 minutes and then
        sleep for that long as well.
        """
        lifetime = 30 * 60
        while True:
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
        # while to complete.
        devices = await wait_with_token(
            loop.run_in_executor(None, upnpclient.discover),
            token=self.cancel_token,
            timeout=2 * REPLY_TIMEOUT)
        if not devices:
            self.logger.info("No UPNP-enabled devices found")
            return
        device = devices[0]
        device.WANIPConn1.AddPortMapping(
            NewRemoteHost=device.WANIPConn1.GetExternalIPAddress()['NewExternalIPAddress'],
            NewExternalPort=self.server_address.tcp_port,
            NewProtocol='TCP',
            NewInternalPort=self.server_address.tcp_port,
            NewInternalClient=self.server_address.ip,
            NewEnabled='1',
            NewPortMappingDescription='Created by Py-EVM',
            NewLeaseDuration=lifetime)
        self.logger.info("NAT port forwarding successfully setup")

    async def _start(self) -> None:
        self._server = await asyncio.start_server(
            self.receive_handshake,
            host=self.server_address.ip,
            port=self.server_address.tcp_port,
        )

    async def _close(self) -> None:
        self._server.close()
        await self._server.wait_closed()

    async def run(self) -> None:
        self.logger.info("Running server...")
        await self._start()
        self.logger.info(
            "enode://%s@%s:%s",
            self.privkey.public_key.to_hex()[2:],
            self.server_address.ip,
            self.server_address.tcp_port,
        )
        await self.discovery.create_endpoint()
        asyncio.ensure_future(self.refresh_nat_portmap())
        asyncio.ensure_future(self.discovery.bootstrap())
        asyncio.ensure_future(self.peer_pool.run())
        await self.cancel_token.wait()

    async def stop(self) -> None:
        self.logger.info("Closing server...")
        self.cancel_token.trigger()
        await self.peer_pool.stop()
        await self.discovery.stop()
        await self._close()
        # We run lots of asyncio tasks so this is to make sure they all get a chance to execute
        # and exit cleanly when they notice the cancel token has been triggered.
        await asyncio.sleep(1)

    async def receive_handshake(
            self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            await self._receive_handshake(reader, writer)
        except TimeoutError:
            self.logger.debug("Timeout waiting for handshake")
        except OperationCancelled:
            pass
        except Exception as e:
            self.logger.exception("Unexpected error handling handshake")

    async def _receive_handshake(
            self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.logger.debug("Receiving handshake...")
        # Use reader to read the auth_init msg until EOF
        msg = await wait_with_token(
            reader.read(ENCRYPTED_AUTH_MSG_LEN),
            token=self.cancel_token,
            timeout=REPLY_TIMEOUT,
        )

        # Use decode_authentication(auth_init_message) on auth init msg
        try:
            ephem_pubkey, initiator_nonce, initiator_pubkey = decode_authentication(
                msg, self.privkey)
        # Try to decode as EIP8
        except DecryptionError:
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
                self.logger.warn("Failed to decrypt handshake: %s", e)
                return

        # Get remote's address: IPv4 or IPv6
        ip, socket, *_ = writer.get_extra_info("peername")
        remote_address = Address(ip, socket)

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
            chaindb=self.chaindb,
            network_id=self.network_id
        )

        await self.do_handshake(peer)

    async def do_handshake(self, peer: BasePeer) -> None:
        try:
            # P2P Handshake.
            await peer.do_p2p_handshake(),
        except (HandshakeFailure, TimeoutError) as e:
            self.logger.debug('Unable to finish P2P handshake: %s', str(e))
            return

        try:
            await peer.do_sub_proto_handshake()
        except (HandshakeFailure, asyncio.TimeoutError) as e:
            self.logger.debug('Unable to finish sub protocoll handshake: %s', str(e))
            return

        # Handshake was successful, so run and add peer
        self.peer_pool.start_peer(peer)


def _test() -> None:
    import argparse
    import signal

    from evm.db.backends.memory import MemoryDB
    from evm.chains.ropsten import RopstenChain, ROPSTEN_GENESIS_HEADER

    from p2p.constants import ROPSTEN_BOOTNODES
    from p2p import ecies
    from p2p.peer import ETHPeer

    from trinity.utils.chains import load_nodekey

    from tests.p2p.integration_test_helpers import FakeAsyncChainDB

    parser = argparse.ArgumentParser()
    parser.add_argument('-debug', action="store_true")
    parser.add_argument('-address', type=str, required=True)
    parser.add_argument('-bootnodes', type=str)
    parser.add_argument('-nodekey', type=str)

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s', datefmt='%H:%M:%S')
    log_level = logging.INFO
    if args.debug:
        log_level = logging.DEBUG
    logging.getLogger('p2p.server.Server').setLevel(log_level)

    loop = asyncio.get_event_loop()
    chaindb = FakeAsyncChainDB(MemoryDB())
    chaindb.persist_header(ROPSTEN_GENESIS_HEADER)

    if args.nodekey:
        privkey = load_nodekey(args.nodekey)
    else:
        privkey = ecies.generate_privkey()

    ip, port = args.address.split(':')
    server_address = Address(ip, int(port))
    if args.bootnodes:
        bootstrap_nodes = args.bootnodes.split(',')
    else:
        bootstrap_nodes = ROPSTEN_BOOTNODES

    server = Server(
        privkey,
        server_address,
        chaindb,
        bootstrap_nodes,
        RopstenChain.network_id,
        peer_class=ETHPeer,
    )

    # NOTE: Since we create a different priv/pub key pair every time we run this, remote nodes may
    # try to establish a connection using the pubkey from one of our previous runs, which will
    # result in lots of DecryptionErrors in receive_handshake().
    async def run():
        try:
            await server.run()
        except OperationCancelled:
            pass
        await server.stop()

    for sig in [signal.SIGINT, signal.SIGTERM]:
        loop.add_signal_handler(sig, server.cancel_token.trigger)

    loop.set_debug(True)
    loop.run_until_complete(run())
    loop.close()


if __name__ == "__main__":
    _test()
