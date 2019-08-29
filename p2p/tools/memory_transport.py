import asyncio
import logging
import struct
from typing import Tuple

from cached_property import cached_property

from eth_keys import datatypes

from cancel_token import CancelToken

from p2p._utils import get_devp2p_cmd_id
from p2p.abc import NodeAPI, TransportAPI
from p2p.exceptions import PeerConnectionLost
from p2p.tools.asyncio_streams import get_directly_connected_streams
from p2p.transport_state import TransportState


CONNECTION_LOST_ERRORS = (
    asyncio.IncompleteReadError,
    ConnectionResetError,
    BrokenPipeError,
)


class MemoryTransport(TransportAPI):
    logger = logging.getLogger('p2p.tools.memory_transport.MemoryTransport')
    read_state = TransportState.IDLE

    def __init__(self,
                 remote: NodeAPI,
                 private_key: datatypes.PrivateKey,
                 reader: asyncio.StreamReader,
                 writer: asyncio.StreamWriter) -> None:
        self.remote = remote
        self._private_key = private_key
        self._reader = reader
        self._writer = writer

    @classmethod
    def connected_pair(cls,
                       alice: Tuple[NodeAPI, datatypes.PrivateKey],
                       bob: Tuple[NodeAPI, datatypes.PrivateKey],
                       ) -> Tuple[TransportAPI, TransportAPI]:
        (
            (alice_reader, alice_writer),
            (bob_reader, bob_writer),
        ) = get_directly_connected_streams()
        alice_remote, alice_private_key = alice
        bob_remote, bob_private_key = bob
        alice_transport = cls(
            alice_remote,
            alice_private_key,
            alice_reader,
            alice_writer,
        )
        bob_transport = cls(bob_remote, bob_private_key, bob_reader, bob_writer)
        return alice_transport, bob_transport

    @cached_property
    def public_key(self) -> datatypes.PublicKey:
        return self._private_key.public_key

    async def read(self, n: int, token: CancelToken) -> bytes:
        self.logger.debug("Waiting for %s bytes from %s", n, self.remote)
        try:
            return await token.cancellable_wait(
                self._reader.readexactly(n),
            )
        except CONNECTION_LOST_ERRORS as err:
            raise PeerConnectionLost from err

    def write(self, data: bytes) -> None:
        self._writer.write(data)

    async def recv(self, token: CancelToken) -> bytes:
        self.read_state = TransportState.HEADER
        try:
            encoded_size = await self.read(3, token)
        except asyncio.CancelledError:
            self.read_state = TransportState.IDLE
            raise
        (size,) = struct.unpack(b'>I', b'\x00' + encoded_size)
        self.read_state = TransportState.BODY
        data = await self.read(size, token)
        self.read_state = TransportState.IDLE
        return data

    def send(self, header: bytes, body: bytes) -> None:
        (size,) = struct.unpack(b'>I', b'\x00' + header[:3])
        if self.is_closing:
            cmd_id = get_devp2p_cmd_id(body)
            self.logger.error(
                "Attempted to send msg with cmd id %d to disconnected peer %s", cmd_id, self)
            return
        self.write(header[:3] + body[:size])

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
