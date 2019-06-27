import asyncio
from typing import cast, Any, Callable, Tuple


class MockTransport:
    def __init__(self) -> None:
        self._is_closing = False

    def close(self) -> None:
        self._is_closing = True

    def is_closing(self) -> bool:
        return self._is_closing


class MockStreamWriter:
    def __init__(self, write_target: Callable[..., None]) -> None:
        self._target = write_target
        self.transport = MockTransport()

    def write(self, *args: Any, **kwargs: Any) -> None:
        self._target(*args, **kwargs)

    def close(self) -> None:
        self.transport.close()


TConnectedStreams = Tuple[
    Tuple[asyncio.StreamReader, asyncio.StreamWriter],
    Tuple[asyncio.StreamReader, asyncio.StreamWriter],
]


def get_directly_connected_streams() -> TConnectedStreams:
    bob_reader = asyncio.StreamReader()
    alice_reader = asyncio.StreamReader()
    # Link the alice's writer to the bob's reader, and the bob's writer to the
    # alice's reader.
    bob_writer = MockStreamWriter(alice_reader.feed_data)
    alice_writer = MockStreamWriter(bob_reader.feed_data)
    return (
        (alice_reader, cast(asyncio.StreamWriter, alice_writer)),
        (bob_reader, cast(asyncio.StreamWriter, bob_writer)),
    )
