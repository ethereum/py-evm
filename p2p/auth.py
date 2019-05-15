import asyncio
import logging
import os
import random
import struct
from typing import Tuple

import sha3

import rlp
from rlp import sedes

from eth_keys import (
    datatypes,
    keys,
)

from eth_hash.auto import keccak

from cancel_token import CancelToken

from p2p import ecies
from p2p import kademlia
from p2p.constants import REPLY_TIMEOUT
from p2p.exceptions import (
    BadAckMessage,
    DecryptionError,
    HandshakeFailure,
)
from p2p._utils import (
    sxor,
)

from .constants import (
    AUTH_ACK_LEN,
    AUTH_MSG_LEN,
    ENCRYPTED_AUTH_MSG_LEN,
    ENCRYPTED_AUTH_ACK_LEN,
    ENCRYPT_OVERHEAD_LENGTH,
    HASH_LEN,
    PUBKEY_LEN,
    SIGNATURE_LEN,
    SUPPORTED_RLPX_VERSION,
)


async def handshake(
        remote: kademlia.Node,
        privkey: datatypes.PrivateKey,
        token: CancelToken) -> Tuple[bytes, bytes, sha3.keccak_256, sha3.keccak_256, asyncio.StreamReader, asyncio.StreamWriter]:  # noqa: E501
    """
    Perform the auth handshake with given remote.

    Returns the established secrets and the StreamReader/StreamWriter pair already connected to
    the remote.
    """
    use_eip8 = False
    initiator = HandshakeInitiator(remote, privkey, use_eip8, token)
    reader, writer = await initiator.connect()
    try:
        aes_secret, mac_secret, egress_mac, ingress_mac = await _handshake(
            initiator, reader, writer, token)
    except Exception:
        # Note: This is one of two places where we manually handle closing the
        # reader/writer connection pair in the event of an error during the
        # peer connection and handshake process.
        # See `p2p.peer.handshake` for the other.
        if not reader.at_eof():
            reader.feed_eof()
        writer.close()
        await asyncio.sleep(0)
        raise

    return aes_secret, mac_secret, egress_mac, ingress_mac, reader, writer


async def _handshake(initiator: 'HandshakeInitiator', reader: asyncio.StreamReader,
                     writer: asyncio.StreamWriter, token: CancelToken,
                     ) -> Tuple[bytes, bytes, sha3.keccak_256, sha3.keccak_256]:
    """See the handshake() function above.

    This code was factored out into this helper so that we can create Peers with directly
    connected readers/writers for our tests.
    """
    initiator_nonce = keccak(os.urandom(HASH_LEN))
    auth_msg = initiator.create_auth_message(initiator_nonce)
    auth_init = initiator.encrypt_auth_message(auth_msg)

    if writer.transport.is_closing():
        raise HandshakeFailure("Error during handshake with {initiator.remote!r}. Writer closed.")

    writer.write(auth_init)

    auth_ack = await token.cancellable_wait(
        reader.read(ENCRYPTED_AUTH_ACK_LEN),
        timeout=REPLY_TIMEOUT)

    if reader.at_eof():
        # This is what happens when Parity nodes have blacklisted us
        # (https://github.com/ethereum/py-evm/issues/901).
        raise HandshakeFailure(f"{initiator.remote!r} disconnected before sending auth ack")

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
    _is_initiator = False

    def __init__(
            self, remote: kademlia.Node, privkey: datatypes.PrivateKey,
            use_eip8: bool, token: CancelToken) -> None:
        self.remote = remote
        self.privkey = privkey
        self.ephemeral_privkey = ecies.generate_privkey()
        self.use_eip8 = use_eip8
        self.cancel_token = token

    @property
    def ephemeral_pubkey(self) -> datatypes.PublicKey:
        return self.ephemeral_privkey.public_key

    @property
    def pubkey(self) -> datatypes.PublicKey:
        return self.privkey.public_key

    async def connect(self) -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        return await self.cancel_token.cancellable_wait(
            asyncio.open_connection(host=self.remote.address.ip, port=self.remote.address.tcp_port),
            timeout=REPLY_TIMEOUT)

    def derive_secrets(self,
                       initiator_nonce: bytes,
                       responder_nonce: bytes,
                       remote_ephemeral_pubkey: datatypes.PublicKey,
                       auth_init_ciphertext: bytes,
                       auth_ack_ciphertext: bytes
                       ) -> Tuple[bytes, bytes, sha3.keccak_256, sha3.keccak_256]:
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
        # egress-mac = sha3.keccak_256(mac-secret ^ recipient-nonce || auth-sent-init)
        mac1 = sha3.keccak_256(
            sxor(mac_secret, responder_nonce) + auth_init_ciphertext
        )
        # ingress-mac = sha3.keccak_256(mac-secret ^ initiator-nonce || auth-recvd-ack)
        mac2 = sha3.keccak_256(
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
        if self.use_eip8:
            auth_msg = encrypt_eip8_msg(auth_message, self.remote.pubkey)
        else:
            auth_msg = ecies.encrypt(auth_message, self.remote.pubkey)
        return auth_msg

    def create_auth_message(self, nonce: bytes) -> bytes:
        ecdh_shared_secret = ecies.ecdh_agree(self.privkey, self.remote.pubkey)
        secret_xor_nonce = sxor(ecdh_shared_secret, nonce)
        S = self.ephemeral_privkey.sign_msg_hash(secret_xor_nonce).to_bytes()

        if self.use_eip8:
            data = rlp.encode(
                [S, self.pubkey.to_bytes(), nonce, SUPPORTED_RLPX_VERSION], sedes=eip8_auth_sedes)
            return _pad_eip8_data(data)
        else:
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
            raise BadAckMessage(f"Auth ack msg too short: {len(ciphertext)}")
        elif len(ciphertext) == ENCRYPTED_AUTH_ACK_LEN:
            eph_pubkey, nonce, _ = decode_ack_plain(ciphertext, self.privkey)
        else:
            eph_pubkey, nonce, _ = decode_ack_eip8(ciphertext, self.privkey)
        return eph_pubkey, nonce


class HandshakeResponder(HandshakeBase):

    def create_auth_ack_message(self, nonce: bytes) -> bytes:
        if self.use_eip8:
            data = rlp.encode(
                (self.ephemeral_pubkey.to_bytes(), nonce, SUPPORTED_RLPX_VERSION),
                sedes=eip8_ack_sedes)
            msg = _pad_eip8_data(data)
        else:
            # Unused, according to EIP-8, but must be included nevertheless.
            token_flag = b'\x00'
            msg = self.ephemeral_pubkey.to_bytes() + nonce + token_flag
        return msg

    def encrypt_auth_ack_message(self, ack_message: bytes) -> bytes:
        if self.use_eip8:
            auth_ack = encrypt_eip8_msg(ack_message, self.remote.pubkey)
        else:
            auth_ack = ecies.encrypt(ack_message, self.remote.pubkey)
        return auth_ack


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


def _pad_eip8_data(data: bytes) -> bytes:
    # Pad with random amount of data, as per
    # https://github.com/ethereum/EIPs/blob/master/EIPS/eip-8.md:
    # "Adding a random amount in range [100, 300] is recommended to vary the size of the
    # packet"
    return data + os.urandom(random.randint(100, 300))


def encrypt_eip8_msg(msg: bytes, pubkey: datatypes.PublicKey) -> bytes:
    prefix = struct.pack('>H', len(msg) + ENCRYPT_OVERHEAD_LENGTH)
    suffix = ecies.encrypt(msg, pubkey, shared_mac_data=prefix)
    return prefix + suffix


def decode_ack_plain(
        ciphertext: bytes, privkey: datatypes.PrivateKey) -> Tuple[datatypes.PublicKey, bytes, int]:
    """Decrypts and decodes a legacy pre-EIP-8 auth ack message.

    Returns the remote's ephemeral pubkey, nonce and protocol version.
    """
    message = ecies.decrypt(ciphertext, privkey)
    if len(message) != AUTH_ACK_LEN:
        raise BadAckMessage(f"Unexpected size for ack message: {len(message)}")
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
        raise BadAckMessage(f"Unexpected size for auth message: {len(message)}")
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


def decode_authentication(ciphertext: bytes,
                          privkey: datatypes.PrivateKey
                          ) -> Tuple[datatypes.PublicKey, bytes, datatypes.PublicKey]:
    """
    Decrypts and decodes the ciphertext msg.
    Returns the initiator's ephemeral pubkey, nonce, and pubkey.
    """
    if len(ciphertext) < ENCRYPTED_AUTH_MSG_LEN:
        raise DecryptionError(f"Auth msg too short: {len(ciphertext)}")
    elif len(ciphertext) == ENCRYPTED_AUTH_MSG_LEN:
        sig, initiator_pubkey, initiator_nonce, _ = decode_auth_plain(
            ciphertext, privkey)
    else:
        sig, initiator_pubkey, initiator_nonce, _ = decode_auth_eip8(
            ciphertext, privkey)

    # recover initiator ephemeral pubkey from sig
    #   S(ephemeral-privk, ecdh-shared-secret ^ nonce)
    shared_secret = ecies.ecdh_agree(privkey, initiator_pubkey)

    ephem_pubkey = sig.recover_public_key_from_msg_hash(
        sxor(shared_secret, initiator_nonce))

    return ephem_pubkey, initiator_nonce, initiator_pubkey
