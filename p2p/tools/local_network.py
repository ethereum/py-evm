import asyncio
import logging
import random
from typing import (
    Dict,
    Iterable,
    NamedTuple,
    Tuple,
)

from p2p.cancel_token import CancelToken, wait_with_token
from p2p.exceptions import OperationCancelled
from p2p.service import BaseService


class Address(NamedTuple):
    transport: str
    host: str
    port: int

    def __repr__(self):
        return '<%s %s>' % (self.__class__.__name__, self)

    def __str__(self):
        return '%s:%s:%s' % (self.transport, self.host, self.port)


class MemoryTransport(asyncio.Transport):
    """
    Direct connection between a StreamWriter and StreamReader.
    """

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

    def __init__(self, address: Address, reader: asyncio.StreamReader) -> None:
        super().__init__(reader)
        self._address = address
        self._queue = asyncio.Queue()

    @property
    def queue(self):
        return self._queue

    def get_extra_info(self, name, default=None):
        if name == 'peername':
            return (self._address.host, self._address.port)
        else:
            return super().get_extra_info(name, default)

    def write(self, data: bytes) -> None:
        super().write(data)
        self._queue.put_nowait(len(data))


def addressed_pipe(address) -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:
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


def direct_pipe() -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:
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


logger = logging.getLogger('p2p.testing.network')


class Server:
    """
    Mock version of `asyncio.Server` object.
    """
    def __init__(self, client_connected_cb, address, network):
        self.client_connected_cb = client_connected_cb
        self.address = address
        self.network = network

    def __repr__(self):
        return '<%s %s>' % (self.__class__.__name__, self.address)

    def close(self):
        pass

    async def wait_closed(self):
        return


class Network:
    servers: Dict[int, Server] = None
    connections: Dict[int, Address] = None

    def __init__(self, host, router):
        self.router = router
        self.host = host
        self.servers = {}
        self.connections = {}

    def get_server(self, port):
        try:
            return self.servers[port]
        except KeyError:
            raise ConnectionRefusedError("No server running at {0}:{1}".format(self.host, port))

    def get_open_port(self):
        while True:
            port = random.randint(2**15, 2**16 - 1)
            if port in self.connections:
                continue
            elif port in self.servers:
                continue
            else:
                break
        return port

    async def start_server(self, client_connected_cb, port) -> Server:
        if port in self.servers:
            raise OSError('Address already in use')

        address = Address('tcp', self.host, port)

        server = Server(client_connected_cb, address, self)
        self.servers[port] = server
        return server

    def receive_connection(self, port) -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        address = Address('tcp', self.host, port)
        if port not in self.servers:
            raise ConnectionRefusedError("No server running at {0}:{1}".format(self.host, port))
        if address.port in self.connections:
            raise OSError('Address already in use')

        reader, writer = self.router.get_connected_readers(address)
        return reader, writer

    async def open_connection(self, host, port) -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        if port in self.connections:
            raise OSError('already connected')

        to_address = Address('tcp', host, port)

        to_network = self.router.get_network(host)
        client_reader, server_writer = to_network.receive_connection(port)

        from_port = self.get_open_port()
        from_address = Address('tcp', self.host, from_port)

        server_reader, client_writer = self.router.get_connected_readers(from_address)
        self.connections[from_port] = to_address

        server = to_network.get_server(port)
        asyncio.ensure_future(server.client_connected_cb(server_reader, server_writer))

        return client_reader, client_writer


async def _connect_network(reader, writer, queue, token):
    logger.info('NETWORK CONNECTED')
    try:
        while not reader.at_eof():
            logger.info('WAITING ON QUEUE')
            size = await wait_with_token(queue.get(), token=token)
            data = await wait_with_token(reader.readexactly(size), token=token)
            writer.write(data)
            logger.info('DATA RECEIVED: size %s', size)
            await wait_with_token(writer.drain(), token=token)
        else:
            writer.write_eof()
    except OperationCancelled:
        writer.write_eof()


class Router(BaseService):
    networks: Dict[str, Network]

    def __init__(self, default_host: str=None):
        super().__init__()
        self.networks = {}
        self.connections = {}

        if default_host is None:
            self.default_host = '127.0.0.1'
        else:
            self.default_host = default_host

    def get_network(self, host):
        if host not in self.networks:
            self.networks[host] = Network(host, self)
        return self.networks[host]

    def get_connected_readers(self, address):
        external_reader, internal_writer = direct_pipe()
        internal_reader, external_writer = addressed_pipe(address)

        token = self.cancel_token.chain(CancelToken('something'))
        connection = asyncio.ensure_future(_connect_network(
            internal_reader, internal_writer, external_writer.transport.queue, token,
        ))
        self.connections[token] = connection

        return (external_reader, external_writer)

    #
    # Asyncio API
    #
    async def start_server(self, client_connected_cb, host, port) -> Server:
        network = self.get_network(host)
        return await network.start_server(client_connected_cb, port)

    async def open_connection(self, host, port) -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        network = self.get_network(self.default_host)
        try:
            return await network.open_connection(host, port)
        except ConnectionRefusedError as err:
            # if we fail to connect to the specified host, check if there is a
            # server running on `0.0.0.0` and connect to that.
            catch_all_network = self.get_network('0.0.0.0')
            try:
                return await catch_all_network.open_connection('0.0.0.0', port)
            except ConnectionRefusedError:
                pass
            raise err

    async def _run(self):
        while not self.cancel_token.triggered:
            await asyncio.sleep(0.02)

    async def _cleanup(self):
        # all of the cancel tokens *should* be triggered already so we just
        # wait for the networking processes to complete.
        if self.connections:
            await asyncio.wait(
                self.connections.values(),
                timeout=1,
                return_when=asyncio.ALL_COMPLETED
            )
