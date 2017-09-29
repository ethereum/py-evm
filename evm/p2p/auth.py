import asyncio
import logging
import os
import random
import sha3
import struct

import rlp
from rlp import sedes

from eth_keys import keys

from evm.utils.keccak import (
    keccak,
)
from evm.p2p import ecies
from evm.p2p.constants import (
    AUTH_ACK_LEN,
    AUTH_MSG_LEN,
    ENCRYPTED_AUTH_ACK_LEN,
    ENCRYPTED_AUTH_MSG_LEN,
    HASH_LEN,
    PUBKEY_LEN,
    SIGNATURE_LEN,
    SUPPORTED_RLPX_VERSION,
)
from evm.p2p.peer import Peer
from evm.p2p.utils import (
    sxor,
)


@asyncio.coroutine
def handshake(remote, privkey):
    """Perform the auth handshake with the given remote and return a Peer ready to be used.

    The Peer will be configured with the shared secrets established during the handshake.
    """
    initiator = HandshakeInitiator(remote, privkey)
    reader, writer = yield from initiator.connect()

    initiator_nonce = keccak(os.urandom(HASH_LEN))
    auth_msg = initiator.create_auth_message(initiator_nonce)
    auth_init = initiator.encrypt_auth_message(auth_msg)
    writer.write(auth_init)

    auth_ack = yield from reader.read(ENCRYPTED_AUTH_ACK_LEN)

    ephemeral_pubkey, responder_nonce = initiator.decode_auth_ack_message(auth_ack)
    aes_secret, mac_secret, egress_mac, ingress_mac = initiator.derive_secrets(
        initiator_nonce,
        responder_nonce,
        ephemeral_pubkey,
        auth_init,
        auth_ack
    )

    peer = Peer(remote=remote, privkey=privkey, reader=reader, writer=writer,
                aes_secret=aes_secret, mac_secret=mac_secret, egress_mac=egress_mac,
                ingress_mac=ingress_mac)
    peer.send_hello()
    return peer


class HandshakeBase:
    logger = logging.getLogger("evm.p2p.peer.Handshake")
    got_eip8_auth = False

    def __init__(self, remote, privkey):
        self.remote = remote
        self.privkey = privkey
        self.ephemeral_privkey = ecies.generate_privkey()

    @property
    def ephemeral_pubkey(self):
        return self.ephemeral_privkey.public_key

    @property
    def pubkey(self):
        return self.privkey.public_key

    @asyncio.coroutine
    def connect(self):
        reader, writer = yield from asyncio.open_connection(
            host=self.remote.address.ip, port=self.remote.address.tcp_port)
        return reader, writer

    def derive_secrets(self, initiator_nonce, responder_nonce,
                       remote_ephemeral_pubkey, auth_init_ciphertext, auth_ack_ciphertext):
        """Derive base secrets from ephemeral key agreement."""
        # ecdhe-shared-secret = ecdh.agree(ephemeral-privkey, remote-ephemeral-pubk)
        ecdhe_shared_secret = ecies.ecdh_agree(
            self.ephemeral_privkey, remote_ephemeral_pubkey)

        # shared-secret = sha3(ecdhe-shared-secret || sha3(nonce || initiator-nonce))
        shared_secret = keccak(
            ecdhe_shared_secret + keccak(responder_nonce + initiator_nonce))

        # aes-secret = sha3(ecdhe-shared-secret || shared-secret)
        aes_secret = keccak(ecdhe_shared_secret + shared_secret)

        # mac-secret = sha3(ecdhe-shared-secret || aes-secret)
        mac_secret = keccak(ecdhe_shared_secret + aes_secret)

        # setup sha3 instances for the MACs
        # egress-mac = sha3.update(mac-secret ^ recipient-nonce || auth-sent-init)
        mac1 = sha3.keccak_256(sxor(mac_secret, responder_nonce) + auth_init_ciphertext)
        # ingress-mac = sha3.update(mac-secret ^ initiator-nonce || auth-recvd-ack)
        mac2 = sha3.keccak_256(sxor(mac_secret, initiator_nonce) + auth_ack_ciphertext)

        if self._is_initiator:
            egress_mac, ingress_mac = mac1, mac2
        else:
            egress_mac, ingress_mac = mac2, mac1

        return aes_secret, mac_secret, egress_mac, ingress_mac


class HandshakeInitiator(HandshakeBase):
    _is_initiator = True

    def encrypt_auth_message(self, auth_message):
        return ecies.encrypt(auth_message, self.remote.pubkey)

    def create_auth_message(self, nonce):
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

    def decode_auth_ack_message(self, ciphertext):
        if len(ciphertext) < ENCRYPTED_AUTH_ACK_LEN:
            raise ValueError("Auth ack msg too short: {}".format(len(ciphertext)))
        elif len(ciphertext) == ENCRYPTED_AUTH_ACK_LEN:
            eph_pubkey, nonce, version = decode_ack_plain(ciphertext, self.privkey)
        else:
            eph_pubkey, nonce, version = decode_ack_eip8(ciphertext, self.privkey)
            self.got_eip8_auth = True
        return eph_pubkey, nonce


class HandshakeResponder(HandshakeBase):
    _is_initiator = False

    def create_auth_ack_message(self, nonce):
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

    def encrypt_auth_ack_message(self, ack_message):
        if self.got_eip8_auth:
            # The EIP-8 version has an authenticated length prefix.
            prefix = struct.pack('>H', len(ack_message) + ecies.encrypt_overhead_length)
            suffix = ecies.encrypt(
                ack_message, self.remote.pubkey, shared_mac_data=prefix)
            auth_ack = prefix + suffix
        else:
            auth_ack = ecies.encrypt(ack_message, self.remote.pubkey)
        return auth_ack

    def decode_authentication(self, ciphertext):
        """Decrypts and decodes the auth_init message.

        Returns the initiator's ephemeral pubkey and nonce.
        """
        if len(ciphertext) < ENCRYPTED_AUTH_MSG_LEN:
            raise ValueError("Auth msg too short: {}".format(len(ciphertext)))
        elif len(ciphertext) == ENCRYPTED_AUTH_MSG_LEN:
            sig, initiator_pubkey, initiator_nonce, version = decode_auth_plain(
                ciphertext, self.privkey)
        else:
            sig, initiator_pubkey, initiator_nonce, version = decode_auth_eip8(
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


def decode_ack_plain(ciphertext, privkey):
    """Decrypts and decodes a legacy pre-EIP-8 auth ack message.

    Returns the remote's ephemeral pubkey, nonce and protocol version.
    """
    message = ecies.decrypt(ciphertext, privkey)
    if len(message) != AUTH_ACK_LEN:
        raise ValueError("Unexpected size for ack message: {}".format(len(message)))
    eph_pubkey = keys.PublicKey(message[:PUBKEY_LEN])
    nonce = message[PUBKEY_LEN: PUBKEY_LEN + HASH_LEN]
    return eph_pubkey, nonce, SUPPORTED_RLPX_VERSION


def decode_ack_eip8(ciphertext, privkey):
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


def decode_auth_plain(ciphertext, privkey):
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


def decode_auth_eip8(ciphertext, privkey):
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
