import asyncio
from typing import Any, Dict, Sequence, Tuple


class MemoryProtocol(asyncio.Protocol):
    def __init__(self) -> None:
        self._closed_event = asyncio.Event()

    async def _drain_helper(self) -> None:
        pass

    @property
    async def _closed(self) -> None:
        await self._closed_event.wait()


class MemoryTransport(asyncio.WriteTransport):
    """
    A fake version of the ``asyncio.BaseTransport``:

    https://docs.python.org/3/library/asyncio-protocol.html#asyncio.BaseTransport
    """
    def __init__(self,
                 reader: asyncio.StreamReader,
                 extra: Dict[str, Any] = None) -> None:
        self._is_closing = False
        self._reader = reader
        super().__init__(extra)

    #
    # BaseTransport methods
    #
    # methods we don't overwrite because they already raise NotImplementedError
    # and we don't need them
    # - set_protocol
    # - get_protocol
    def close(self) -> None:
        self._is_closing = True

    def is_closing(self) -> bool:
        return self._is_closing or self._reader.at_eof()

    #
    # WriteTransport methods
    #
    # methods we don't overwrite because they already raise NotImplementedError
    # and we don't need them
    # - set_write_buffer_limits
    # - get_write_buffer_size
    def write(self, data: bytes) -> None:
        self._reader.feed_data(data)

    def writelines(self, list_of_data: Sequence[bytes]) -> None:
        data = b''.join(list_of_data)
        self.write(data)

    def write_eof(self) -> None:
        self._is_closing = True

    def can_write_eof(self) -> bool:
        return True

    def abort(self) -> None:
        self._is_closing = True


TConnectedStreams = Tuple[
    Tuple[asyncio.StreamReader, asyncio.StreamWriter],
    Tuple[asyncio.StreamReader, asyncio.StreamWriter],
]


def get_directly_connected_streams(alice_extra_info: Dict[str, Any] = None,
                                   bob_extra_info: Dict[str, Any] = None,
                                   loop: asyncio.AbstractEventLoop = None) -> TConnectedStreams:
    alice_reader = asyncio.StreamReader()
    bob_reader = asyncio.StreamReader()

    alice_transport = MemoryTransport(bob_reader, extra=alice_extra_info)
    bob_transport = MemoryTransport(alice_reader, extra=bob_extra_info)

    alice_protocol = MemoryProtocol()
    bob_protocol = MemoryProtocol()

    # Link the alice's writer to the bob's reader, and the bob's writer to the
    # alice's reader.
    bob_writer = asyncio.StreamWriter(bob_transport, bob_protocol, alice_reader, loop=None)
    alice_writer = asyncio.StreamWriter(alice_transport, alice_protocol, bob_reader, loop=None)
    return (
        (alice_reader, alice_writer),
        (bob_reader, bob_writer),
    )
