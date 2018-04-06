import asyncio
import logging
import secrets

from typing import Tuple
from eth_keys import datatypes

from evm.db.chain import AsyncChainDB
from p2p.auth import (
    decode_auth_plain,
    decode_auth_eip8,
    HandshakeResponder,
)
from p2p.cancel_token import CancelToken
from p2p.constants import (
    ENCRYPTED_AUTH_MSG_LEN,
    HASH_LEN,
)
from p2p.discovery import DiscoveryProtocol
from p2p.ecies import ecdh_agree
from p2p.exceptions import OperationCancelled
from p2p.kademlia import (
    Address,
    Node,
)
from p2p.peer import (
    ETHPeer,
    PeerPool,
)
from p2p.utils import sxor


class Server:
    """Server listening for incoming connections"""
    logger = logging.getLogger("p2p.server.Server")

    def __init__(self,
                 privkey: datatypes.PrivateKey,
                 server_address: Address,
                 chaindb: AsyncChainDB
                 ) -> None:
        self.cancel_token = CancelToken('Server')
        self.chaindb = chaindb
        self.privkey = privkey
        self.server_address = server_address
        discovery = DiscoveryProtocol(self.privkey, self.server_address, bootstrap_nodes=[])
        self.peer_pool = PeerPool(ETHPeer, self.chaindb, 1, self.privkey, discovery)

    async def run(self) -> None:
        self.logger.info("Running server...")
        loop = asyncio.get_event_loop()
        factory = asyncio.start_server(
            self.receive_handshake, host=self.server_address.ip, port=self.server_address.udp_port)
        asyncio.ensure_future(factory)

        while not self.cancel_token.triggered:
            try:
                loop.run_forever()
            except OperationCancelled:
                break

    async def stop(self) -> None:
        self.logger.info("Closing server...")
        self.cancel_token.trigger()
        asyncio.ensure_future(self.peer_pool.stop())

    async def receive_handshake(
            self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        # Use reader to read the auth_init msg until EOF
        msg = await reader.read()

        # Use HandshakeResponder.decode_authentication(auth_init_message) on auth init msg
        ephem_pubkey, initiator_nonce, initiator_pubkey = decode_authentication(msg, self.privkey)

        # Get remote's address: IPv4 or IPv6
        peername = writer.get_extra_info("peername")
        ip = peername[0]
        port = peername[1]
        remote_address = Address(ip, port)

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
        eth_peer = ETHPeer(
            remote=initiator_remote, privkey=self.privkey, reader=reader,
            writer=writer, aes_secret=aes_secret, mac_secret=mac_secret,
            egress_mac=egress_mac, ingress_mac=ingress_mac, chaindb=self.chaindb,
            network_id=1
        )
        self.peer_pool.add_peer(eth_peer)


def decode_authentication(ciphertext: bytes,
                          privkey: datatypes.PrivateKey
                          ) -> Tuple[datatypes.PublicKey, bytes, datatypes.PublicKey]:
    """
    Decrypts and decodes the ciphertext msg.
    Returns the initiator's ephemeral pubkey, nonce, and pubkey.
    """
    if len(ciphertext) < ENCRYPTED_AUTH_MSG_LEN:
        raise ValueError("Auth msg too short: {}".format(len(ciphertext)))
    elif len(ciphertext) == ENCRYPTED_AUTH_MSG_LEN:
        sig, initiator_pubkey, initiator_nonce, _ = decode_auth_plain(
            ciphertext, privkey)
    else:
        sig, initiator_pubkey, initiator_nonce, _ = decode_auth_eip8(
            ciphertext, privkey)

    # recover initiator ephemeral pubkey from sig
    #   S(ephemeral-privk, ecdh-shared-secret ^ nonce)
    shared_secret = ecdh_agree(privkey, initiator_pubkey)

    ephem_pubkey = sig.recover_public_key_from_msg_hash(
        sxor(shared_secret, initiator_nonce))

    return ephem_pubkey, initiator_nonce, initiator_pubkey
