import asyncio
import struct
from typing import Tuple

from cached_property import cached_property

from eth_keys import datatypes

from cancel_token import CancelToken

from p2p.kademlia import Node
from p2p.tools.asyncio_streams import get_directly_connected_streams
from p2p.exceptions import PeerConnectionLost


class MemoryTransport:
    def __init__(self,
                 remote: Node,
                 private_key: datatypes.PrivateKey,
                 reader: asyncio.StreamReader,
                 writer: asyncio.StreamWriter,
                 token: CancelToken = None) -> None:
        self.remote = remote
        self._private_key = private_key
        self._reader = reader
        self._writer = writer

        if token is None:
            token = CancelToken('MemoryTransport')
        self._token = token

    @classmethod
    def connected_pair(cls,
                       alice: Tuple[Node, datatypes.PrivateKey, CancelToken],
                       bob: Tuple[Node, datatypes.PrivateKey, CancelToken],
                       ) -> Tuple['MemoryTransport', 'MemoryTransport']:
        (
            (alice_reader, alice_writer),
            (bob_reader, bob_writer),
        ) = get_directly_connected_streams()
        alice_remote, alice_private_key, alice_token = alice
        bob_remote, bob_private_key, bob_token = bob
        alice_transport = cls(
            alice_remote,
            alice_private_key,
            alice_reader,
            alice_writer,
            alice_token,
        )
        bob_transport = cls(bob_remote, bob_private_key, bob_reader, bob_writer, bob_token)
        return alice_transport, bob_transport

    @cached_property
    def public_key(self) -> datatypes.PublicKey:
        return self._private_key.public_key

    async def read(self, n: int, token: CancelToken) -> bytes:
        try:
            return await token.cancellable_wait(
                self._reader.readexactly(n),
                timeout=2,
            )
        except (asyncio.IncompleteReadError, ConnectionResetError, BrokenPipeError) as err:
            raise PeerConnectionLost from err

    def write(self, data: bytes) -> None:
        self._writer.write(data)

    async def recv(self, token: CancelToken) -> bytes:
        encoded_size = await self.read(3, token)
        (size,) = struct.unpack(b'>I', b'\x00' + encoded_size)
        data = await self.read(size, token)
        return data

    def send(self, header: bytes, body: bytes) -> None:
        (size,) = struct.unpack(b'>I', b'\x00' + header[:3])
        if self.is_closing:
            raise PeerConnectionLost("transport closed")
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
