import asyncio
import struct
from typing import Tuple

from cached_property import cached_property
from cancel_token import CancelToken
from eth_keys import datatypes
from eth_utils import (
    get_extended_debug_logger,
)

from p2p.abc import MessageAPI, NodeAPI, TransportAPI
from p2p.exceptions import PeerConnectionLost
from p2p.message import Message
from p2p.session import Session
from p2p.tools.asyncio_streams import get_directly_connected_streams
from p2p.transport_state import TransportState


CONNECTION_LOST_ERRORS = (
    asyncio.IncompleteReadError,
    ConnectionResetError,
    BrokenPipeError,
)


class MemoryTransport(TransportAPI):
    logger = get_extended_debug_logger('p2p.tools.memory_transport.MemoryTransport')
    read_state = TransportState.IDLE

    def __init__(self,
                 remote: NodeAPI,
                 private_key: datatypes.PrivateKey,
                 reader: asyncio.StreamReader,
                 writer: asyncio.StreamWriter) -> None:
        self.remote = remote
        self.session = Session(remote)
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
        self.logger.debug2("Waiting for %s bytes from %s", n, self.remote)
        try:
            return await token.cancellable_wait(
                self._reader.readexactly(n),
            )
        except CONNECTION_LOST_ERRORS as err:
            raise PeerConnectionLost from err

    def write(self, data: bytes) -> None:
        self._writer.write(data)

    async def recv(self, token: CancelToken) -> MessageAPI:
        self.read_state = TransportState.HEADER
        try:
            encoded_sizes = await self.read(8, token)
        except asyncio.CancelledError:
            self.read_state = TransportState.IDLE
            raise
        header_size, body_size = struct.unpack('>II', encoded_sizes)
        self.read_state = TransportState.BODY
        header = await self.read(header_size, token)
        body = await self.read(body_size, token)
        self.read_state = TransportState.IDLE
        return Message(header, body)

    def send(self, message: MessageAPI) -> None:
        header_size = len(message.header)
        body_size = len(message.body)

        encoded_sizes = struct.pack('>II', header_size, body_size)

        if self.is_closing:
            self.logger.error(
                f"Attempted to send msg with cmd id {message.command_id} to "
                f"disconnected peer {self.remote}"
            )
            return
        self.write(encoded_sizes + message.header + message.body)

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
