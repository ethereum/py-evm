import asyncio
import hmac
import logging
import secrets
import struct
from typing import cast

import sha3

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from cached_property import cached_property

from cancel_token import CancelToken

from eth_keys import datatypes

from eth_utils import big_endian_to_int

from eth.tools.logging import ExtendedDebugLogger

from p2p import auth
from p2p._utils import (
    get_devp2p_cmd_id,
    roundup_16,
    sxor,
)
from p2p.auth import (
    decode_authentication,
    HandshakeResponder,
)
from p2p.constants import (
    CONN_IDLE_TIMEOUT,
    ENCRYPTED_AUTH_MSG_LEN,
    HASH_LEN,
    HEADER_LEN,
    MAC_LEN,
    REPLY_TIMEOUT,
)
from p2p.exceptions import (
    HandshakeFailure,
    DecryptionError,
    MalformedMessage,
    PeerConnectionLost,
    UnreachablePeer,
)
from p2p.kademlia import Address, Node


class Transport:
    logger = cast(ExtendedDebugLogger, logging.getLogger('p2p.connection.Transport'))

    def __init__(self,
                 remote: Node,
                 private_key: datatypes.PrivateKey,
                 reader: asyncio.StreamReader,
                 writer: asyncio.StreamWriter,
                 aes_secret: bytes,
                 mac_secret: bytes,
                 egress_mac: sha3.keccak_256,
                 ingress_mac: sha3.keccak_256) -> None:
        self.remote = remote

        self._private_key = private_key

        # Encryption and Cryptography *stuff*
        self._egress_mac = egress_mac
        self._ingress_mac = ingress_mac

        self._reader = reader
        self._writer = writer

        # FIXME: Insecure Encryption: https://github.com/ethereum/devp2p/issues/32
        iv = b"\x00" * 16
        aes_secret = aes_secret
        mac_secret = mac_secret

        aes_cipher = Cipher(algorithms.AES(aes_secret), modes.CTR(iv), default_backend())
        self._aes_enc = aes_cipher.encryptor()
        self._aes_dec = aes_cipher.decryptor()

        mac_cipher = Cipher(algorithms.AES(mac_secret), modes.ECB(), default_backend())
        self._mac_enc = mac_cipher.encryptor().update

    @classmethod
    async def connect(cls,
                      remote: Node,
                      private_key: datatypes.PrivateKey,
                      token: CancelToken) -> 'Transport':
        """Perform the auth and P2P handshakes with the given remote.

        Return an instance of the given peer_class (must be a subclass of
        BasePeer) connected to that remote in case both handshakes are
        successful and at least one of the sub-protocols supported by
        peer_class is also supported by the remote.

        Raises UnreachablePeer if we cannot connect to the peer or
        HandshakeFailure if the remote disconnects before completing the
        handshake or if none of the sub-protocols supported by us is also
        supported by the remote.
        """
        try:
            (aes_secret,
             mac_secret,
             egress_mac,
             ingress_mac,
             reader,
             writer
             ) = await auth.handshake(remote, private_key, token)
        except (ConnectionRefusedError, OSError) as e:
            raise UnreachablePeer(f"Can't reach {remote!r}") from e

        return cls(
            remote=remote,
            private_key=private_key,
            reader=reader,
            writer=writer,
            aes_secret=aes_secret,
            mac_secret=mac_secret,
            egress_mac=egress_mac,
            ingress_mac=ingress_mac,
        )

    @classmethod
    async def receive_connection(cls,
                                 reader: asyncio.StreamReader,
                                 writer: asyncio.StreamWriter,
                                 private_key: datatypes.PrivateKey,
                                 token: CancelToken) -> 'Transport':
        try:
            msg = await token.cancellable_wait(
                reader.readexactly(ENCRYPTED_AUTH_MSG_LEN),
                timeout=REPLY_TIMEOUT,
            )
        except asyncio.IncompleteReadError as err:
            raise HandshakeFailure from err

        try:
            ephem_pubkey, initiator_nonce, initiator_pubkey = decode_authentication(
                msg,
                private_key,
            )
        except DecryptionError as non_eip8_err:
            # Try to decode as EIP8
            msg_size = big_endian_to_int(msg[:2])
            remaining_bytes = msg_size - ENCRYPTED_AUTH_MSG_LEN + 2

            try:
                msg += await token.cancellable_wait(
                    reader.readexactly(remaining_bytes),
                    timeout=REPLY_TIMEOUT,
                )
            except asyncio.IncompleteReadError as err:
                raise HandshakeFailure from err

            try:
                ephem_pubkey, initiator_nonce, initiator_pubkey = decode_authentication(
                    msg,
                    private_key,
                )
            except DecryptionError as eip8_err:
                raise HandshakeFailure(
                    f"Failed to decrypt both EIP8 handshake: {eip8_err}  and "
                    f"non-EIP8 handshake: {non_eip8_err}"
                )
            else:
                got_eip8 = True
        else:
            got_eip8 = False

        peername = writer.get_extra_info("peername")
        if peername is None:
            socket = writer.get_extra_info("socket")
            sockname = writer.get_extra_info("sockname")
            raise HandshakeFailure(
                "Received incoming connection with no remote information:"
                f"socket={repr(socket)}  sockname={sockname}"
            )

        ip, socket, *_ = peername
        remote_address = Address(ip, socket)

        cls.logger.debug("Receiving handshake from %s", remote_address)

        initiator_remote = Node(initiator_pubkey, remote_address)

        responder = HandshakeResponder(initiator_remote, private_key, got_eip8, token)

        responder_nonce = secrets.token_bytes(HASH_LEN)

        auth_ack_msg = responder.create_auth_ack_message(responder_nonce)
        auth_ack_ciphertext = responder.encrypt_auth_ack_message(auth_ack_msg)

        # Use the `writer` to send the reply to the remote
        writer.write(auth_ack_ciphertext)
        await token.cancellable_wait(writer.drain())

        # Call `HandshakeResponder.derive_shared_secrets()` and use return values to create `Peer`
        aes_secret, mac_secret, egress_mac, ingress_mac = responder.derive_secrets(
            initiator_nonce=initiator_nonce,
            responder_nonce=responder_nonce,
            remote_ephemeral_pubkey=ephem_pubkey,
            auth_init_ciphertext=msg,
            auth_ack_ciphertext=auth_ack_ciphertext
        )

        transport = cls(
            remote=initiator_remote,
            private_key=private_key,
            reader=reader,
            writer=writer,
            aes_secret=aes_secret,
            mac_secret=mac_secret,
            egress_mac=egress_mac,
            ingress_mac=ingress_mac,
        )
        return transport

    @cached_property
    def public_key(self) -> datatypes.PublicKey:
        return self._private_key.public_key

    async def read(self, n: int, token: CancelToken) -> bytes:
        self.logger.debug2("Waiting for %s bytes from %s", n, self.remote)
        try:
            return await token.cancellable_wait(
                self._reader.readexactly(n),
                timeout=CONN_IDLE_TIMEOUT,
            )
        except (asyncio.IncompleteReadError, ConnectionResetError, BrokenPipeError) as e:
            raise PeerConnectionLost(repr(e))

    def write(self, data: bytes) -> None:
        self._writer.write(data)

    async def recv(self, token: CancelToken) -> bytes:
        header_data = await self.read(HEADER_LEN + MAC_LEN, token)
        try:
            header = self._decrypt_header(header_data)
        except DecryptionError as err:
            self.logger.debug(
                "Bad message header from peer %s: Error: %r",
                self, err,
            )
            raise MalformedMessage from err
        frame_size = self._get_frame_size(header)
        # The frame_size specified in the header does not include the padding to 16-byte boundary,
        # so need to do this here to ensure we read all the frame's data.
        read_size = roundup_16(frame_size)
        frame_data = await self.read(read_size + MAC_LEN, token)
        try:
            msg = self._decrypt_body(frame_data, frame_size)
        except DecryptionError as err:
            self.logger.debug(
                "Bad message body from peer %s: Error: %r",
                self, err,
            )
            raise MalformedMessage from err

        return msg

    def send(self, header: bytes, body: bytes) -> None:
        cmd_id = get_devp2p_cmd_id(body)
        self.logger.debug2("Sending msg with cmd id %d to %s", cmd_id, self)
        if self.is_closing:
            self.logger.error(
                "Attempted to send msg with cmd id %d to disconnected peer %s", cmd_id, self)
            return

        self.write(self._encrypt(header, body))

    def close(self) -> None:
        """Close this peer's reader/writer streams.

        This will cause the peer to stop in case it is running.

        If the streams have already been closed, do nothing.
        """
        if not self._reader.at_eof():
            self._reader.feed_eof()
        self._writer.close()

    @property
    def is_closing(self) -> bool:
        return self._writer.transport.is_closing()

    def _encrypt(self, header: bytes, frame: bytes) -> bytes:
        if len(header) != HEADER_LEN:
            raise ValueError(f"Unexpected header length: {len(header)}")

        header_ciphertext = self._aes_enc.update(header)
        mac_secret = self._egress_mac.digest()[:HEADER_LEN]
        self._egress_mac.update(sxor(self._mac_enc(mac_secret), header_ciphertext))
        header_mac = self._egress_mac.digest()[:HEADER_LEN]

        frame_ciphertext = self._aes_enc.update(frame)
        self._egress_mac.update(frame_ciphertext)
        fmac_seed = self._egress_mac.digest()[:HEADER_LEN]

        mac_secret = self._egress_mac.digest()[:HEADER_LEN]
        self._egress_mac.update(sxor(self._mac_enc(mac_secret), fmac_seed))
        frame_mac = self._egress_mac.digest()[:HEADER_LEN]

        return header_ciphertext + header_mac + frame_ciphertext + frame_mac

    def _decrypt_header(self, data: bytes) -> bytes:
        if len(data) != HEADER_LEN + MAC_LEN:
            raise ValueError(
                f"Unexpected header length: {len(data)}, expected {HEADER_LEN} + {MAC_LEN}"
            )

        header_ciphertext = data[:HEADER_LEN]
        header_mac = data[HEADER_LEN:]
        mac_secret = self._ingress_mac.digest()[:HEADER_LEN]
        aes = self._mac_enc(mac_secret)[:HEADER_LEN]
        self._ingress_mac.update(sxor(aes, header_ciphertext))
        expected_header_mac = self._ingress_mac.digest()[:HEADER_LEN]
        if not hmac.compare_digest(expected_header_mac, header_mac):
            raise DecryptionError(
                f'Invalid header mac: expected {expected_header_mac}, got {header_mac}'
            )
        return self._aes_dec.update(header_ciphertext)

    def _decrypt_body(self, data: bytes, body_size: int) -> bytes:
        read_size = roundup_16(body_size)
        if len(data) < read_size + MAC_LEN:
            raise ValueError(
                f'Insufficient body length; Got {len(data)}, wanted {read_size} + {MAC_LEN}'
            )

        frame_ciphertext = data[:read_size]
        frame_mac = data[read_size:read_size + MAC_LEN]

        self._ingress_mac.update(frame_ciphertext)
        fmac_seed = self._ingress_mac.digest()[:MAC_LEN]
        self._ingress_mac.update(sxor(self._mac_enc(fmac_seed), fmac_seed))
        expected_frame_mac = self._ingress_mac.digest()[:MAC_LEN]
        if not hmac.compare_digest(expected_frame_mac, frame_mac):
            raise DecryptionError(
                f'Invalid frame mac: expected {expected_frame_mac}, got {frame_mac}'
            )
        return self._aes_dec.update(frame_ciphertext)[:body_size]

    def _get_frame_size(self, header: bytes) -> int:
        # The frame size is encoded in the header as a 3-byte int, so before we unpack we need
        # to prefix it with an extra byte.
        encoded_size = b'\x00' + header[:3]
        (size,) = struct.unpack(b'>I', encoded_size)
        return size
