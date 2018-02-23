import asyncio
import logging
import os
import random
import struct
from typing import Tuple

import rlp
from rlp import sedes

from eth_keys import (
    datatypes,
    keys,
)

from eth_hash.main import (
    PreImage,
)
from eth_hash.auto import (
    keccak as keccak_with_digest,
)

from eth_utils import (
    keccak,
)

from p2p import ecies
from p2p import kademlia
from p2p.utils import (
    sxor,
)

from .constants import (
    AUTH_ACK_LEN,
    AUTH_MSG_LEN,
    ENCRYPTED_AUTH_ACK_LEN,
    ENCRYPTED_AUTH_MSG_LEN,
    ENCRYPT_OVERHEAD_LENGTH,
    HASH_LEN,
    PUBKEY_LEN,
    SIGNATURE_LEN,
    SUPPORTED_RLPX_VERSION,
)


async def handshake(remote: kademlia.Node, privkey: datatypes.PrivateKey) -> Tuple[
    bytes, bytes, PreImage, PreImage, asyncio.StreamReader, asyncio.StreamWriter]:  # noqa: E501
    """
    Perform the auth handshake with given remote.

    Returns the established secrets and the StreamReader/StreamWriter pair already connected to
    the remote.
    """
    initiator = HandshakeInitiator(remote, privkey)
    reader, writer = await initiator.connect()
    aes_secret, mac_secret, egress_mac, ingress_mac = await _handshake(
        initiator, reader, writer)
    return aes_secret, mac_secret, egress_mac, ingress_mac, reader, writer


async def _handshake(initiator: 'HandshakeInitiator', reader: asyncio.StreamReader,
                     writer: asyncio.StreamWriter
                     ) -> Tuple[bytes, bytes, PreImage, PreImage]:
    """See the handshake() function above.

    This code was factored out into this helper so that we can create Peers with directly
    connected readers/writers for our tests.
    """
    initiator_nonce = keccak(os.urandom(HASH_LEN))
    auth_msg = initiator.create_auth_message(initiator_nonce)
    auth_init = initiator.encrypt_auth_message(auth_msg)
    writer.write(auth_init)

    auth_ack = await reader.read(ENCRYPTED_AUTH_ACK_LEN)

    ephemeral_pubkey, responder_nonce = initiator.decode_auth_ack_message(auth_ack)
    aes_secret, mac_secret, egress_mac, ingress_mac = initiator.derive_secrets(
        initiator_nonce,
        responder_nonce,
        ephemeral_pubkey,
        auth_init,
        auth_ack
    )

    return aes_secret, mac_secret, egress_mac, ingress_mac


class HandshakeBase:
    logger = logging.getLogger("p2p.peer.Handshake")
    got_eip8_auth = False
    _is_initiator = False

    def __init__(self, remote: kademlia.Node, privkey: datatypes.PrivateKey) -> None:
        self.remote = remote
        self.privkey = privkey
        self.ephemeral_privkey = ecies.generate_privkey()

    @property
    def ephemeral_pubkey(self) -> datatypes.PublicKey:
        return self.ephemeral_privkey.public_key

    @property
    def pubkey(self) -> datatypes.PublicKey:
        return self.privkey.public_key

    async def connect(self) -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        return await asyncio.open_connection(
            host=self.remote.address.ip, port=self.remote.address.tcp_port)

    def derive_secrets(self,
                       initiator_nonce: bytes,
                       responder_nonce: bytes,
                       remote_ephemeral_pubkey: datatypes.PublicKey,
                       auth_init_ciphertext: bytes,
                       auth_ack_ciphertext: bytes
                       ) -> Tuple[bytes, bytes, PreImage, PreImage]:
        """Derive base secrets from ephemeral key agreement."""
        # ecdhe-shared-secret = ecdh.agree(ephemeral-privkey, remote-ephemeral-pubk)
        ecdhe_shared_secret = ecies.ecdh_agree(
            self.ephemeral_privkey, remote_ephemeral_pubkey)

        # shared-secret = keccak(ecdhe-shared-secret || keccak(nonce || initiator-nonce))
        shared_secret = keccak(
            ecdhe_shared_secret + keccak(responder_nonce + initiator_nonce))

        # aes-secret = keccak(ecdhe-shared-secret || shared-secret)
        aes_secret = keccak(ecdhe_shared_secret + shared_secret)

        # mac-secret = keccak(ecdhe-shared-secret || aes-secret)
        mac_secret = keccak(ecdhe_shared_secret + aes_secret)

        # setup keccak instances for the MACs
        # egress-mac = keccak_with_digest.new(mac-secret ^ recipient-nonce || auth-sent-init)
        mac1 = keccak_with_digest.new(
            sxor(mac_secret, responder_nonce) + auth_init_ciphertext
        )
        # ingress-mac = keccak_with_digest.new(mac-secret ^ initiator-nonce || auth-recvd-ack)
        mac2 = keccak_with_digest.new(
            sxor(mac_secret, initiator_nonce) + auth_ack_ciphertext
        )

        if self._is_initiator:
            egress_mac, ingress_mac = mac1, mac2
        else:
            egress_mac, ingress_mac = mac2, mac1

        return aes_secret, mac_secret, egress_mac, ingress_mac


class HandshakeInitiator(HandshakeBase):
    _is_initiator = True

    def encrypt_auth_message(self, auth_message: bytes) -> bytes:
        return ecies.encrypt(auth_message, self.remote.pubkey)

    def create_auth_message(self, nonce: bytes) -> bytes:
        ecdh_shared_secret = ecies.ecdh_agree(self.privkey, self.remote.pubkey)
        secret_xor_nonce = sxor(ecdh_shared_secret, nonce)

        # S(ephemeral-privk, ecdh-shared-secret ^ nonce)
        S = self.ephemeral_privkey.sign_msg_hash(secret_xor_nonce).to_bytes()

        # S || H(ephemeral-pubk) || pubk || nonce || 0x0
        return (
            S +
            keccak(self.ephemeral_pubkey.to_bytes()) +
            self.pubkey.to_bytes() +
            nonce +
            b'\x00'
        )

    def decode_auth_ack_message(self, ciphertext: bytes) -> Tuple[datatypes.PublicKey, bytes]:
        if len(ciphertext) < ENCRYPTED_AUTH_ACK_LEN:
            raise ValueError("Auth ack msg too short: {}".format(len(ciphertext)))
        elif len(ciphertext) == ENCRYPTED_AUTH_ACK_LEN:
            eph_pubkey, nonce, _ = decode_ack_plain(ciphertext, self.privkey)
        else:
            eph_pubkey, nonce, _ = decode_ack_eip8(ciphertext, self.privkey)
            self.got_eip8_auth = True
        return eph_pubkey, nonce


class HandshakeResponder(HandshakeBase):

    def create_auth_ack_message(self, nonce: bytes) -> bytes:
        if self.got_eip8_auth:
            data = rlp.encode(
                (self.ephemeral_pubkey.to_bytes(), nonce, SUPPORTED_RLPX_VERSION),
                sedes=eip8_ack_sedes)
            # Pad with random amount of data. The amount needs to be at least 100 bytes to make
            # the message distinguishable from pre-EIP-8 handshakes.
            msg = data + os.urandom(random.randint(100, 250))
        else:
            # Unused, according to EIP-8, but must be included nevertheless.
            token_flag = b'\x00'
            msg = self.ephemeral_pubkey.to_bytes() + nonce + token_flag
        return msg

    def encrypt_auth_ack_message(self, ack_message: bytes) -> bytes:
        if self.got_eip8_auth:
            # The EIP-8 version has an authenticated length prefix.
            prefix = struct.pack('>H', len(ack_message) + ENCRYPT_OVERHEAD_LENGTH)
            suffix = ecies.encrypt(
                ack_message, self.remote.pubkey, shared_mac_data=prefix)
            auth_ack = prefix + suffix
        else:
            auth_ack = ecies.encrypt(ack_message, self.remote.pubkey)
        return auth_ack

    def decode_authentication(self, ciphertext: bytes) -> Tuple[datatypes.PublicKey, bytes]:
        """Decrypts and decodes the auth_init message.

        Returns the initiator's ephemeral pubkey and nonce.
        """
        if len(ciphertext) < ENCRYPTED_AUTH_MSG_LEN:
            raise ValueError("Auth msg too short: {}".format(len(ciphertext)))
        elif len(ciphertext) == ENCRYPTED_AUTH_MSG_LEN:
            sig, initiator_pubkey, initiator_nonce, _ = decode_auth_plain(
                ciphertext, self.privkey)
        else:
            sig, initiator_pubkey, initiator_nonce, _ = decode_auth_eip8(
                ciphertext, self.privkey)
            self.got_eip8_auth = True

        # recover initiator ephemeral pubkey from sig
        #     S(ephemeral-privk, ecdh-shared-secret ^ nonce)
        shared_secret = ecies.ecdh_agree(self.privkey, initiator_pubkey)

        ephem_pubkey = sig.recover_public_key_from_msg_hash(
            sxor(shared_secret, initiator_nonce))

        return ephem_pubkey, initiator_nonce


eip8_ack_sedes = sedes.List(
    [
        sedes.Binary(min_length=64, max_length=64),  # ephemeral pubkey
        sedes.Binary(min_length=32, max_length=32),  # nonce
        sedes.BigEndianInt()                         # version
    ], strict=False)
eip8_auth_sedes = sedes.List(
    [
        sedes.Binary(min_length=65, max_length=65),  # sig
        sedes.Binary(min_length=64, max_length=64),  # pubkey
        sedes.Binary(min_length=32, max_length=32),  # nonce
        sedes.BigEndianInt()                         # version
    ], strict=False)


def decode_ack_plain(
        ciphertext: bytes, privkey: datatypes.PrivateKey) -> Tuple[datatypes.PublicKey, bytes, int]:
    """Decrypts and decodes a legacy pre-EIP-8 auth ack message.

    Returns the remote's ephemeral pubkey, nonce and protocol version.
    """
    message = ecies.decrypt(ciphertext, privkey)
    if len(message) != AUTH_ACK_LEN:
        raise ValueError("Unexpected size for ack message: {}".format(len(message)))
    eph_pubkey = keys.PublicKey(message[:PUBKEY_LEN])
    nonce = message[PUBKEY_LEN: PUBKEY_LEN + HASH_LEN]
    return eph_pubkey, nonce, SUPPORTED_RLPX_VERSION


def decode_ack_eip8(
        ciphertext: bytes, privkey: datatypes.PrivateKey) -> Tuple[datatypes.PublicKey, bytes, int]:
    """Decrypts and decodes a EIP-8 auth ack message.

    Returns the remote's ephemeral pubkey, nonce and protocol version.
    """
    # The length of the actual msg is stored in plaintext on the first two bytes.
    encoded_size = ciphertext[:2]
    auth_ack = ciphertext[2:]
    message = ecies.decrypt(auth_ack, privkey, shared_mac_data=encoded_size)
    values = rlp.decode(message, sedes=eip8_ack_sedes, strict=False)
    pubkey_bytes, nonce, version = values[:3]
    return keys.PublicKey(pubkey_bytes), nonce, version


def decode_auth_plain(ciphertext: bytes, privkey: datatypes.PrivateKey) -> Tuple[
        datatypes.Signature, datatypes.PublicKey, bytes, int]:
    """Decode legacy pre-EIP-8 auth message format"""
    message = ecies.decrypt(ciphertext, privkey)
    if len(message) != AUTH_MSG_LEN:
        raise ValueError("Unexpected size for auth message: {}".format(len(message)))
    signature = keys.Signature(signature_bytes=message[:SIGNATURE_LEN])
    pubkey_start = SIGNATURE_LEN + HASH_LEN
    pubkey = keys.PublicKey(message[pubkey_start: pubkey_start + PUBKEY_LEN])
    nonce_start = pubkey_start + PUBKEY_LEN
    nonce = message[nonce_start: nonce_start + HASH_LEN]
    return signature, pubkey, nonce, SUPPORTED_RLPX_VERSION


def decode_auth_eip8(ciphertext: bytes, privkey: datatypes.PrivateKey) -> Tuple[
        datatypes.Signature, datatypes.PublicKey, bytes, int]:
    """Decode EIP-8 auth message format"""
    # The length of the actual msg is stored in plaintext on the first two bytes.
    encoded_size = ciphertext[:2]
    auth_msg = ciphertext[2:]
    message = ecies.decrypt(auth_msg, privkey, shared_mac_data=encoded_size)
    values = rlp.decode(message, sedes=eip8_auth_sedes, strict=False)
    signature_bytes, pubkey_bytes, nonce, version = values[:4]
    return (
        keys.Signature(signature_bytes=signature_bytes),
        keys.PublicKey(pubkey_bytes),
        nonce,
        version
    )
