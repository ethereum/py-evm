import asyncio
import os
import random
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    NamedTuple,
    List,
    Tuple,
)

import pytest

from p2p.cancel_token import CancelToken, wait_with_token
from p2p.exceptions import OperationCancelled
from p2p.service import BaseService


class Address(NamedTuple):
    host: str
    port: int

    def __repr__(self):
        return '<%s %s>' % (self.__class__.__name__, self)

    def __str__(self):
        return '%s:%s' % (self.host, self.port)


class MemoryTransport(asyncio.Transport):
    """
    Direct connection between a StreamWriter and StreamReader.
    """
    _reader: asyncio.StreamReader

    def __init__(self, reader: asyncio.StreamReader) -> None:
        super().__init__()
        self._reader = reader

    def write(self, data: bytes) -> None:
        self._reader.feed_data(data)

    def writelines(self, data: Iterable[bytes]) -> None:
        for line in data:
            self.write(line)
            self.write(b'\n')

    def write_eof(self) -> None:
        self._reader.feed_eof()

    def can_write_eof(self) -> bool:
        return True

    def is_closing(self) -> bool:
        return False

    def close(self) -> None:
        self.write_eof()


class AddressedTransport(MemoryTransport):
    """
    Direct connection between a StreamWriter and StreamReader.
    """
    _queue: asyncio.Queue

    def __init__(self, address: Address, reader: asyncio.StreamReader) -> None:
        super().__init__(reader)
        self._address = address
        self._queue = asyncio.Queue()

    @property
    def queue(self) -> asyncio.Queue:
        return self._queue

    def get_extra_info(self, name: str, default=None):
        if name == 'peername':
            return (self._address.host, self._address.port)
        else:
            return super().get_extra_info(name, default)

    def write(self, data: bytes) -> None:
        super().write(data)
        self._queue.put_nowait(len(data))


ReaderWriterPair = Tuple[asyncio.StreamReader, asyncio.StreamWriter]


def addressed_pipe(address: Address) -> ReaderWriterPair:
    reader = asyncio.StreamReader()

    transport = AddressedTransport(address, reader)
    protocol = asyncio.StreamReaderProtocol(reader)

    writer = asyncio.StreamWriter(
        transport=transport,
        protocol=protocol,
        reader=reader,
        loop=asyncio.get_event_loop(),
    )
    return reader, writer


def direct_pipe() -> ReaderWriterPair:
    reader = asyncio.StreamReader()

    transport = MemoryTransport(reader)
    protocol = asyncio.StreamReaderProtocol(reader)

    writer = asyncio.StreamWriter(
        transport=transport,
        protocol=protocol,
        reader=reader,
        loop=asyncio.get_event_loop(),
    )
    return reader, writer


async def _connect_streams(
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        queue: asyncio.Queue,
        token: CancelToken) -> None:
    try:
        while not token.triggered:
            if reader.at_eof():
                break

            try:
                size = queue.get_nowait()
            except asyncio.QueueEmpty:
                await asyncio.sleep(0)
                continue
            data = await wait_with_token(reader.readexactly(size), token=token)
            writer.write(data)
            queue.task_done()
            await wait_with_token(writer.drain(), token=token)
    except OperationCancelled:
        pass
    finally:
        writer.write_eof()

    if reader.at_eof():
        reader.feed_eof()


class Router(BaseService):
    hosts: Dict[str, 'Host']
    networks = Dict[str, 'Network']
    connections = Dict[CancelToken, asyncio.Task]

    def __init__(self):
        super().__init__()
        self.hosts = {}
        self.networks = {}
        self.connections = {}

    #
    # Service API
    #
    async def _run(self) -> None:
        while not self.cancel_token.triggered:
            await asyncio.sleep(0.02)

    async def _cleanup(self) -> None:
        # all of the cancel tokens *should* be triggered already so we just
        # wait for the networking processes to complete.
        if self.connections:
            await asyncio.wait(
                self.connections.values(),
                timeout=2,
                return_when=asyncio.ALL_COMPLETED
            )

    #
    # Connections API
    #
    def get_host(self, host: str) -> 'Host':
        if host not in self.hosts:
            self.hosts[host] = Host(host, self)
        return self.hosts[host]

    def get_network(self, name: str) -> 'Network':
        if name not in self.networks:
            self.networks[name] = Network(name, self)
        return self.networks[name]

    def get_connected_readers(self, address: Address) -> ReaderWriterPair:
        external_reader, internal_writer = direct_pipe()
        internal_reader, external_writer = addressed_pipe(address)

        token = CancelToken(str(address)).chain(self.cancel_token)
        connection = asyncio.ensure_future(_connect_streams(
            internal_reader, internal_writer, external_writer.transport.queue, token,
        ))
        self.connections[token] = connection

        return (external_reader, external_writer)


ConnectionCallback = Callable[[asyncio.StreamReader, asyncio.StreamWriter], Any]


class Server(asyncio.AbstractServer):
    """
    Mock version of `asyncio.Server` object.
    """
    connections: List[asyncio.StreamWriter]

    def __init__(
            self,
            client_connected_cb: ConnectionCallback,
            address: Address) -> None:
        self.client_connected_cb = client_connected_cb
        self.address = address
        self.connections = []

    def __repr__(self) -> str:
        return '<%s %s>' % (self.__class__.__name__, self.address)

    def close(self) -> None:
        for writer in self.connections:
            writer.write_eof()

    async def wait_closed(self) -> None:
        await asyncio.wait(
            tuple(writer.drain() for writer in self.connections),
            timeout=0.01,
            return_when=asyncio.ALL_COMPLETED
        )

    def add_connection(self, writer: asyncio.StreamWriter) -> None:
        self.connections.append(writer)


class Network:
    router: Router
    name: str
    _default_host: str = None

    def __init__(self, name: str, router: Router, default_host: str=None):
        self.name = name
        self.router = router
        self.default_host = default_host

    @property
    def default_host(self) -> str:
        if self._default_host is not None:
            return self._default_host
        else:
            return os.environ.get('P2P_DEFAULT_HOST', '127.0.0.1')

    @default_host.setter
    def default_host(self, value: str) -> None:
        self._default_host = value

    #
    # Asyncio API
    #
    async def start_server(
            self,
            client_connected_cb: ConnectionCallback,
            host: str,
            port: int) -> Server:
        host = self.router.get_host(host)
        return await host.start_server(client_connected_cb, port)

    async def open_connection(
            self,
            host: str,
            port: int) -> ReaderWriterPair:
        client_host = self.router.get_host(self.default_host)
        try:
            return await client_host.open_connection(host, port)
        except ConnectionRefusedError as err:
            # if we fail to connect to the specified host, check if there is a
            # server running on `0.0.0.0` and connect to that.
            catch_all_host = self.router.get_host('0.0.0.0')
            try:
                return await catch_all_host.open_connection('0.0.0.0', port)
            except ConnectionRefusedError:
                pass
            raise err


class Host:
    servers: Dict[int, Server] = None
    connections: Dict[int, Address] = None

    def __init__(self, host: str, router: Router) -> None:
        self.router = router
        self.host = host
        self.servers = {}
        self.connections = {}

    def get_server(self, port: int) -> Server:
        try:
            return self.servers[port]
        except KeyError:
            raise ConnectionRefusedError("No server running at {0}:{1}".format(self.host, port))

    def _get_open_port(self) -> int:
        while True:
            port = random.randint(2**15, 2**16 - 1)
            if port in self.connections:
                continue
            elif port in self.servers:
                continue
            else:
                break
        return port

    async def start_server(self, client_connected_cb: ConnectionCallback, port: int) -> Server:
        if port in self.servers:
            raise OSError('Address already in use')

        address = Address(self.host, port)

        server = Server(client_connected_cb, address)
        self.servers[port] = server
        return server

    def receive_connection(self, port: int) -> ReaderWriterPair:
        address = Address(self.host, port)
        if port not in self.servers:
            raise ConnectionRefusedError("No server running at {0}:{1}".format(self.host, port))
        elif address.port in self.connections:
            raise OSError('Address already in use')

        reader, writer = self.router.get_connected_readers(address)

        server = self.servers[port]
        server.add_connection(writer)

        return reader, writer

    async def open_connection(self, host: str, port: int) -> ReaderWriterPair:
        if port in self.connections:
            raise OSError('already connected')

        to_address = Address(host, port)

        to_host = self.router.get_host(host)
        client_reader, server_writer = to_host.receive_connection(port)

        from_port = self._get_open_port()
        from_address = Address(self.host, from_port)

        server_reader, client_writer = self.router.get_connected_readers(from_address)
        self.connections[from_port] = to_address

        server = to_host.get_server(port)
        asyncio.ensure_future(server.client_connected_cb(server_reader, server_writer))

        return client_reader, client_writer


@pytest.fixture
async def router():
    router = Router()
    try:
        asyncio.ensure_future(router.run())
        yield router
    finally:
        await asyncio.wait_for(router.cancel(), timeout=2)


@pytest.fixture
def network(router, monkeypatch):
    network = router.get_network('localhost')
    network.default_host = '127.0.0.1'

    monkeypatch.setattr(asyncio, 'start_server', network.start_server)
    monkeypatch.setattr(asyncio, 'open_connection', network.open_connection)
    return network
