import asyncio
import os
import logging
import secrets
import sys

from typing import Tuple
from eth_keys import (
    datatypes,
    keys,
)
from eth_utils import (
    decode_hex,
    keccak,
)

from p2p.auth import (
    HandshakeResponder,
    decode_auth_plain,
    decode_auth_eip8,
)
from p2p.cancel_token import CancelToken
from p2p.constants import (
    ENCRYPTED_AUTH_MSG_LEN,
    HASH_LEN,
)
from p2p.ecies import ecdh_agree
from p2p.exceptions import OperationCancelled
from p2p.kademlia import (
    Address,
    Node,
)
from p2p.peer import PeerPool, BasePeer, PeerPoolSubscriber, ETHPeer, LESPeer
from p2p.utils import sxor


class Server(PeerPoolSubscriber):
    """Server listening for incoming connections"""
    logger = logging.getLogger("p2p.server.Server")
    
    def __init__(self, privkey: datatypes.PrivateKey, server_addr: Tuple[str, str], peer_pool: PeerPool) -> None:
        self.cancel_token = CancelToken('Server')
        self.incoming_connections = []
        self.peer_pool = peer_pool
        self.peer_pool.subscribe(self)
        self._running_peers = set()
        self.privkey = privkey
        self._server_address = server_addr

    def register_peer(self, peer: ETHPeer) -> None:
        pass

    async def stop(self) -> None:
        self.logger.info("Closing server...")
        self.cancel_token.trigger()
        self.peer_pool.unsubscribe(self)
        await asyncio.sleep(1)
        while self._running_peers:
            self.logger.debug("Waiting for %d running peers to finish", len(self._running_peers))

    async def run(self) -> None:
        self.logger.info("Running server...")
        loop = asyncio.get_event_loop()
        factory = asyncio.start_server(self.receive_handshake, *self._server_address)
        asyncio.ensure_future(factory)
        
        while not self.cancel_token.triggered:
            try:
                loop.run_forever()
            except:
                self.logger.error("Unexpected error.")
            await asyncio.sleep(1)

    async def receive_handshake(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        # Use reader to read the auth_init msg until EOF
        msg = await reader.read()

        # Use HandshakeResponder.decode_authentication(auth_init_message) on auth init msg
        ephem_pubkey, initiator_nonce, initiator_pubkey = _decode_authentication(msg, self.privkey)

        # Get remote's address 
        ip, udp, _, _ = writer.get_extra_info("peername")
        remote_address = Address(ip, udp)

        # Create a `HandshakeResponder(remote: kademlia.Node, privkey: datatypes.PrivateKey)` instance
        initiator_remote = Node(initiator_pubkey, remote_address)
        responder = HandshakeResponder(initiator_remote, self.privkey)

        # Call `HandshakeResponder.create_auth_ack_message(nonce: bytes)` to create the reply
        responder_nonce = secrets.token_bytes(HASH_LEN) 
        auth_ack_msg = responder.create_auth_ack_message(nonce=responder_nonce) 
        auth_ack_ciphertext = responder.encrypt_auth_ack_message(auth_ack_msg)

        # Use the `writer` to send the reply to the remote
        writer.write(auth_ack_ciphertext)
        await writer.drain()
        
        # Use `HandshakeResponder.derive_shared_secrets()` and use the return values to instantiate a `Peer` instance
        aes_secret, mac_secret, egress_mac, ingress_mac = responder.derive_secrets(
            initiator_nonce=initiator_nonce,
            responder_nonce=responder_nonce,
            remote_ephemeral_pubkey=ephem_pubkey,
            auth_init_ciphertext=msg,
            auth_ack_ciphertext=auth_ack_ciphertext
        )

        # Store peer creation data in incoming_connections[]
        # TODO register peer in PeerPool
        peer = (aes_secret, mac_secret, initiator_nonce, ephem_pubkey)
        self.incoming_connections.append(peer)


def _decode_authentication(ciphertext: bytes,
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
