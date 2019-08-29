import asyncio
import collections
import logging
from typing import (
    AsyncIterator,
    cast,
    DefaultDict,
    Dict,
    Sequence,
    Tuple,
    Type,
    Union,
)

from async_generator import asynccontextmanager

from cancel_token import CancelToken

from eth_utils.toolz import cons

from eth.tools.logging import ExtendedDebugLogger

from p2p._utils import (
    get_devp2p_cmd_id,
)
from p2p.abc import (
    CommandAPI,
    MultiplexerAPI,
    NodeAPI,
    ProtocolAPI,
    TransportAPI,
    TProtocol,
)
from p2p.cancellable import CancellableMixin
from p2p.exceptions import (
    UnknownProtocol,
    UnknownProtocolCommand,
)
from p2p.p2p_proto import BaseP2PProtocol
from p2p.protocol import Protocol
from p2p.resource_lock import ResourceLock
from p2p.transport_state import TransportState
from p2p.typing import Payload


async def stream_transport_messages(transport: TransportAPI,
                                    base_protocol: BaseP2PProtocol,
                                    *protocols: ProtocolAPI,
                                    token: CancelToken = None,
                                    ) -> AsyncIterator[Tuple[ProtocolAPI, CommandAPI, Payload]]:
    """
    Streams 3-tuples of (Protocol, Command, Payload) over the provided `Transport`
    """
    # A cache for looking up the proper protocol instance for a given command
    # id.
    cmd_id_cache: Dict[int, ProtocolAPI] = {}

    while not transport.is_closing:
        raw_msg = await transport.recv(token)

        cmd_id = get_devp2p_cmd_id(raw_msg)

        if cmd_id not in cmd_id_cache:
            if cmd_id < base_protocol.cmd_length:
                cmd_id_cache[cmd_id] = base_protocol
            else:
                for protocol in protocols:
                    if cmd_id < protocol.cmd_id_offset + protocol.cmd_length:
                        cmd_id_cache[cmd_id] = protocol
                        break
                else:
                    protocol_infos = '  '.join(tuple(
                        f"{proto.name}@{proto.version}[offset={proto.cmd_id_offset},cmd_length={proto.cmd_length}]"  # noqa: E501
                        for proto in cons(base_protocol, protocols)
                    ))
                    raise UnknownProtocolCommand(
                        f"No protocol found for cmd_id {cmd_id}: Available "
                        f"protocol/offsets are: {protocol_infos}"
                    )

        msg_proto = cmd_id_cache[cmd_id]
        cmd = msg_proto.cmd_by_id[cmd_id]
        msg = cmd.decode(raw_msg)

        yield msg_proto, cmd, msg

        # yield to the event loop for a moment to allow `transport.is_closing`
        # a chance to update.
        await asyncio.sleep(0)


class Multiplexer(CancellableMixin, MultiplexerAPI):
    logger = cast(ExtendedDebugLogger, logging.getLogger('p2p.multiplexer.Multiplexer'))

    _multiplex_token: CancelToken

    _transport: TransportAPI
    _msg_counts: DefaultDict[Type[CommandAPI], int]

    _protocol_locks: ResourceLock
    _protocol_queues: Dict[Type[ProtocolAPI], 'asyncio.Queue[Tuple[CommandAPI, Payload]]']

    def __init__(self,
                 transport: TransportAPI,
                 base_protocol: BaseP2PProtocol,
                 protocols: Sequence[ProtocolAPI],
                 token: CancelToken = None,
                 max_queue_size: int = 4096) -> None:
        if token is None:
            loop = None
        else:
            loop = token.loop
        base_token = CancelToken(f'multiplexer[{transport.remote}]', loop=loop)

        if token is None:
            self.cancel_token = base_token
        else:
            self.cancel_token = base_token.chain(token)

        self._transport = transport
        # the base `p2p` protocol instance.
        self._base_protocol = base_protocol

        # the sub-protocol instances
        self._protocols = protocols

        # Lock to ensure that multiple call sites cannot concurrently stream
        # messages.
        self._multiplex_lock = asyncio.Lock()

        # Lock management on a per-protocol basis to ensure we only have one
        # stream consumer for each protocol.
        self._protocol_locks = ResourceLock()

        # Each protocol gets a queue where messages for the individual protocol
        # are placed when streamed from the transport
        self._protocol_queues = {
            type(protocol): asyncio.Queue(max_queue_size)
            for protocol
            in self.get_protocols()
        }

        self._msg_counts = collections.defaultdict(int)

    def __str__(self) -> str:
        protocol_infos = ','.join(tuple(
            f"{proto.name}:{proto.version}"
            for proto
            in self.get_protocols()
        ))
        return f"Multiplexer[{protocol_infos}]"

    def __repr__(self) -> str:
        return f"<{self}>"

    #
    # Transport API
    #
    def get_transport(self) -> TransportAPI:
        return self._transport

    #
    # Message Counts
    #
    def get_total_msg_count(self) -> int:
        return sum(self._msg_counts.values())

    #
    # Proxy Transport methods
    #
    @property
    def remote(self) -> NodeAPI:
        return self._transport.remote

    @property
    def is_closing(self) -> bool:
        return self._transport.is_closing

    def close(self) -> None:
        self._transport.close()
        self.cancel_token.trigger()

    #
    # Protocol API
    #
    def has_protocol(self, protocol_identifier: Union[ProtocolAPI, Type[ProtocolAPI]]) -> bool:
        try:
            if isinstance(protocol_identifier, Protocol):
                self.get_protocol_by_type(type(protocol_identifier))
                return True
            elif isinstance(protocol_identifier, type):
                self.get_protocol_by_type(protocol_identifier)
                return True
            else:
                raise TypeError(
                    f"Unsupported protocol value: {protocol_identifier} of type "
                    f"{type(protocol_identifier)}"
                )
        except UnknownProtocol:
            return False

    def get_protocol_by_type(self, protocol_class: Type[TProtocol]) -> TProtocol:
        if issubclass(protocol_class, BaseP2PProtocol):
            return cast(TProtocol, self._base_protocol)

        for protocol in self._protocols:
            if type(protocol) is protocol_class:
                return cast(TProtocol, protocol)
        raise UnknownProtocol(f"No protocol found with type {protocol_class}")

    def get_base_protocol(self) -> BaseP2PProtocol:
        return self._base_protocol

    def get_protocols(self) -> Tuple[ProtocolAPI, ...]:
        return tuple(cons(self._base_protocol, self._protocols))

    #
    # Streaming API
    #
    def stream_protocol_messages(self,
                                 protocol_identifier: Union[ProtocolAPI, Type[ProtocolAPI]],
                                 ) -> AsyncIterator[Tuple[CommandAPI, Payload]]:
        """
        Stream the messages for the specified protocol.
        """
        if isinstance(protocol_identifier, Protocol):
            protocol_class = type(protocol_identifier)
        elif isinstance(protocol_identifier, type) and issubclass(protocol_identifier, Protocol):
            protocol_class = protocol_identifier
        else:
            raise TypeError("Unknown protocol identifier: {protocol}")

        if not self.has_protocol(protocol_class):
            raise UnknownProtocol(f"Unknown protocol '{protocol_class}'")

        if self._protocol_locks.is_locked(protocol_class):
            raise Exception(f"Streaming lock for {protocol_class} is not free.")
        elif not self._multiplex_lock.locked():
            raise Exception("Not multiplexed.")

        # Mostly a sanity check but this ensures we do better than accidentally
        # raising an attribute error in whatever race conditions or edge cases
        # potentially make the `_multiplex_token` unavailable.
        if not hasattr(self, '_multiplex_token'):
            raise Exception("No cancel token found for multiplexing.")

        # We do the wait_iter here so that the call sites in the handshakers
        # that use this don't need to be aware of cancellation tokens.
        return self.wait_iter(
            self._stream_protocol_messages(protocol_class),
            token=self._multiplex_token,
        )

    async def _stream_protocol_messages(self,
                                        protocol_class: Type[Protocol],
                                        ) -> AsyncIterator[Tuple[CommandAPI, Payload]]:
        """
        Stream the messages for the specified protocol.
        """
        async with self._protocol_locks.lock(protocol_class):
            msg_queue = self._protocol_queues[protocol_class]
            if not hasattr(self, '_multiplex_token'):
                raise Exception("Multiplexer is not multiplexed")
            token = self._multiplex_token

            while not self.is_closing and not token.triggered:
                try:
                    # We use an optimistic strategy here of using
                    # `get_nowait()` to reduce the number of times we yield to
                    # the event loop.  Since this is an async generator it will
                    # yield to the loop each time it returns a value so we
                    # don't have to worry about this blocking other processes.
                    yield msg_queue.get_nowait()
                except asyncio.QueueEmpty:
                    yield await self.wait(msg_queue.get(), token=token)

    #
    # Message reading and streaming API
    #
    @asynccontextmanager
    async def multiplex(self) -> AsyncIterator[None]:
        """
        API for running the background task that feeds individual protocol
        queues that allows each individual protocol to stream only its own
        messages.
        """
        # We generate a new token for each time the multiplexer is used to
        # multiplex so that we can reliably cancel it without requiring the
        # master token for the multiplexer to be cancelled.
        async with self._multiplex_lock:
            multiplex_token = CancelToken(
                'multiplex',
                loop=self.cancel_token.loop,
            ).chain(self.cancel_token)

            stop = asyncio.Event()
            self._multiplex_token = multiplex_token
            fut = asyncio.ensure_future(self._do_multiplexing(stop, multiplex_token))
            # wait for the multiplexing to actually start
            try:
                yield
            finally:
                #
                # Prevent corruption of the Transport:
                #
                # On exit the `Transport` can be in a few states:
                #
                # 1. IDLE: between reads
                # 2. HEADER: waiting to read the bytes for the message header
                # 3. BODY: already read the header, waiting for body bytes.
                #
                # In the IDLE case we get a clean shutdown by simply signaling
                # to `_do_multiplexing` that it should exit which is done with
                # an `asyncio.EVent`
                #
                # In the HEADER case we can issue a hard stop either via
                # cancellation or the cancel token.  The read *should* be
                # interrupted without consuming any bytes from the
                # `StreamReader`.
                #
                # In the BODY case we want to give the `Transport.recv` call a
                # moment to finish reading the body after which it will be IDLE
                # and will exit via the IDLE exit mechanism.
                stop.set()

                # If the transport is waiting to read the body of the message
                # we want to give it a moment to finish that read.  Otherwise
                # this leaves the transport in a corrupt state.
                if self._transport.read_state is TransportState.BODY:
                    try:
                        await asyncio.wait_for(fut, timeout=1)
                    except asyncio.TimeoutError:
                        pass

                # After giving the transport an opportunity to shutdown
                # cleanly, we issue a hard shutdown, first via cancellation and
                # then via the cancel token.  This should only end up
                # corrupting the transport in the case where the header data is
                # read but the body data takes too long to arrive which should
                # be very rare and would likely indicate a malicious or broken
                # peer.
                if fut.done():
                    fut.result()
                else:
                    fut.cancel()
                    try:
                        await fut
                    except asyncio.CancelledError:
                        pass

                multiplex_token.trigger()
                del self._multiplex_token

    async def _do_multiplexing(self, stop: asyncio.Event, token: CancelToken) -> None:
        """
        Background task that reads messages from the transport and feeds them
        into individual queues for each of the protocols.
        """
        msg_stream = self.wait_iter(stream_transport_messages(
            self._transport,
            self._base_protocol,
            *self._protocols,
            token=token,
        ), token=token)
        async for protocol, cmd, msg in msg_stream:
            # track total number of messages received for each command type.
            self._msg_counts[type(cmd)] += 1

            queue = self._protocol_queues[type(protocol)]
            try:
                # We must use `put_nowait` here to ensure that in the event
                # that a single protocol queue is full that we don't block
                # other protocol messages getting through.
                queue.put_nowait((cmd, msg))
            except asyncio.QueueFull:
                self.logger.error(
                    (
                        "Multiplexing queue for protocol '%s' full. "
                        "discarding message: %s"
                    ),
                    protocol,
                    cmd,
                )

            if stop.is_set():
                break
