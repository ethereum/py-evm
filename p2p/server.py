import asyncio
import logging
import secrets

from typing import (
    List,
    Type,
)

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
    HANDSHAKE_TIMEOUT,
    HASH_LEN,
)
from p2p.discovery import DiscoveryProtocol
from p2p.exceptions import (
    DecryptionError,
    HandshakeFailure,
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
        discovery = DiscoveryProtocol(
            self.privkey, self.server_address, bootstrap_nodes=bootstrap_nodes)
        self.peer_pool = PeerPool(
            peer_class,
            self.chaindb,
            self.network_id,
            self.privkey,
            discovery,
            min_peers=min_peers,
        )

    async def start(self) -> None:
        self._server = await asyncio.start_server(
            self.receive_handshake,
            host=self.server_address.ip,
            port=self.server_address.tcp_port,
        )

    async def run(self) -> None:
        await self.start()
        self.logger.info("Running server...")
        self.logger.info(
            "enode://%s@%s:%s",
            self.privkey.public_key.to_hex()[2:],
            self.server_address.ip,
            self.server_address.tcp_port,
        )
        await self.cancel_token.wait()
        await self.stop()

    async def stop(self) -> None:
        self.logger.info("Closing server...")
        self.cancel_token.trigger()
        self._server.close()
        await self._server.wait_closed()
        await self.peer_pool.stop()

    async def receive_handshake(
            self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await wait_with_token(
            self._receive_handshake(reader, writer),
            token=self.cancel_token,
            timeout=HANDSHAKE_TIMEOUT,
        )

    async def _receive_handshake(
            self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.logger.debug("Receiving handshake...")
        # Use reader to read the auth_init msg until EOF
        msg = await wait_with_token(
            reader.read(ENCRYPTED_AUTH_MSG_LEN),
            token=self.cancel_token,
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
            )
            ephem_pubkey, initiator_nonce, initiator_pubkey = decode_authentication(
                msg, self.privkey)

        # Get remote's address: IPv4 or IPv6
        ip, socket, *_ = writer.get_extra_info("peername")
        remote_address = Address(ip, socket)

        # Create `HandshakeResponder(remote: kademlia.Node, privkey: datatypes.PrivateKey)` instance
        initiator_remote = Node(initiator_pubkey, remote_address)
        responder = HandshakeResponder(initiator_remote, self.privkey)

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

        await self.do_p2p_handshake(peer)

    async def do_p2p_handshake(self, peer: BasePeer) -> None:
        try:
            # P2P Handshake.
            await peer.do_p2p_handshake(),
        except (HandshakeFailure, asyncio.TimeoutError) as e:
            self.logger.debug('Unable to finish P2P handshake: %s', str(e))
        else:
            # Run peer and add peer.
            self.peer_pool.start_peer(peer)


def _test() -> None:
    import argparse

    from eth_keys import keys
    from eth_utils import (
        decode_hex,
    )

    from evm.db.backends.memory import MemoryDB

    from p2p import ecies
    from p2p.exceptions import (
        OperationCancelled,
    )

    from tests.p2p.dumb_peer import DumbPeer
    from tests.p2p.integration_test_helpers import FakeAsyncChainDB

    parser = argparse.ArgumentParser()
    parser.add_argument('-debug', action="store_true")
    parser.add_argument('-server-address', type=str, required=True)
    parser.add_argument('-bootstrap', '--list', type=str)
    parser.add_argument('-privkey', type=str)

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s', datefmt='%H:%M:%S')
    log_level = logging.INFO
    if args.debug:
        log_level = logging.DEBUG
    logging.getLogger('p2p.server.Server').setLevel(log_level)

    loop = asyncio.get_event_loop()
    chaindb = FakeAsyncChainDB(MemoryDB())

    if args.privkey:
        privkey = keys.PrivateKey(decode_hex(args.privkey))
    else:
        privkey = ecies.generate_privkey()

    ip, port = args.server_address.split(':')
    server_address = Address(ip, port)
    if args.list:
        bootstrap_nodes = args.list.split(',')
    else:
        bootstrap_nodes = []

    server = Server(
        privkey,
        server_address,
        chaindb,
        bootstrap_nodes,
        1,
        peer_class=DumbPeer
    )

    asyncio.ensure_future(server.run())
    asyncio.ensure_future(server.peer_pool.run())

    async def run():
        try:
            while True:
                if len(server.peer_pool.connected_nodes) >= 1:
                    server.logger.debug('peers: %d', len(server.peer_pool.connected_nodes))
                else:
                    server.logger.debug('no peer connected')
                await asyncio.sleep(1)

        except (OperationCancelled, KeyboardInterrupt):
            pass
        await server.peer_pool.stop()
        await server.stop()

    loop.run_until_complete(run())
    loop.close()


if __name__ == "__main__":
    _test()
