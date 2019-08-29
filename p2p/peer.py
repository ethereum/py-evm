from abc import ABC, abstractmethod
import asyncio
import collections
import contextlib
import functools
import logging
from typing import (
    Any,
    cast,
    Dict,
    Iterator,
    List,
    NamedTuple,
    FrozenSet,
    Sequence,
    Tuple,
    Type,
    TYPE_CHECKING,
)

from lahja import EndpointAPI

from cached_property import cached_property

from eth_utils import to_tuple, ValidationError

from eth_keys import datatypes

from cancel_token import CancelToken

from p2p.abc import (
    CommandAPI,
    ConnectionAPI,
    HandshakeReceiptAPI,
    NodeAPI,
    ProtocolAPI,
)
from p2p.constants import BLACKLIST_SECONDS_BAD_PROTOCOL
from p2p.disconnect import DisconnectReason
from p2p.exceptions import (
    UnknownProtocol,
)
from p2p.connection import Connection
from p2p.handshake import (
    negotiate_protocol_handshakes,
    DevP2PHandshakeParams,
    DevP2PReceipt,
    Handshaker,
)
from p2p.service import BaseService
from p2p.p2p_proto import (
    BaseP2PProtocol,
    Disconnect,
    Ping,
)
from p2p.protocol import (
    Command,
    Payload,
)
from p2p.transport import Transport
from p2p.tracking.connection import (
    BaseConnectionTracker,
    NoopConnectionTracker,
)

if TYPE_CHECKING:
    from p2p.peer_pool import BasePeerPool  # noqa: F401


async def handshake(remote: NodeAPI,
                    private_key: datatypes.PrivateKey,
                    p2p_handshake_params: DevP2PHandshakeParams,
                    protocol_handshakers: Tuple[Handshaker, ...],
                    token: CancelToken) -> ConnectionAPI:
    """
    Perform the auth and P2P handshakes with the given remote.

    Return a `Connection` object housing all of the negotiated sub protocols.

    Raises UnreachablePeer if we cannot connect to the peer or
    HandshakeFailure if the remote disconnects before completing the
    handshake or if none of the sub-protocols supported by us is also
    supported by the remote.
    """
    transport = await Transport.connect(
        remote,
        private_key,
        token,
    )

    try:
        multiplexer, devp2p_receipt, protocol_receipts = await negotiate_protocol_handshakes(
            transport=transport,
            p2p_handshake_params=p2p_handshake_params,
            protocol_handshakers=protocol_handshakers,
            token=token,
        )
    except Exception:
        # Note: This is one of two places where we manually handle closing the
        # reader/writer connection pair in the event of an error during the
        # peer connection and handshake process.
        # See `p2p.auth.handshake` for the other.
        transport.close()
        await asyncio.sleep(0)
        raise

    connection = Connection(
        multiplexer=multiplexer,
        devp2p_receipt=devp2p_receipt,
        protocol_receipts=protocol_receipts,
        is_dial_out=True,
    )
    return connection


async def receive_handshake(reader: asyncio.StreamReader,
                            writer: asyncio.StreamWriter,
                            private_key: datatypes.PrivateKey,
                            p2p_handshake_params: DevP2PHandshakeParams,
                            protocol_handshakers: Tuple[Handshaker, ...],
                            token: CancelToken) -> Connection:
    transport = await Transport.receive_connection(
        reader=reader,
        writer=writer,
        private_key=private_key,
        token=token,
    )
    try:
        multiplexer, devp2p_receipt, protocol_receipts = await negotiate_protocol_handshakes(
            transport=transport,
            p2p_handshake_params=p2p_handshake_params,
            protocol_handshakers=protocol_handshakers,
            token=token,
        )
    except Exception:
        # Note: This is one of two places where we manually handle closing the
        # reader/writer connection pair in the event of an error during the
        # peer connection and handshake process.
        # See `p2p.auth.handshake` for the other.
        transport.close()
        await asyncio.sleep(0)
        raise

    connection = Connection(
        multiplexer=multiplexer,
        devp2p_receipt=devp2p_receipt,
        protocol_receipts=protocol_receipts,
        is_dial_out=False,
    )
    return connection


class BasePeerBootManager(BaseService):
    """
    The default boot manager does nothing, simply serving as a hook for other
    protocols which need to perform more complex boot check.
    """
    def __init__(self, peer: 'BasePeer') -> None:
        super().__init__(token=peer.cancel_token, loop=peer.cancel_token.loop)
        self.peer = peer

    async def _run(self) -> None:
        pass


class BasePeerContext:
    client_version_string: str
    listen_port: int
    p2p_version: int

    def __init__(self,
                 client_version_string: str,
                 listen_port: int,
                 p2p_version: int) -> None:
        self.client_version_string = client_version_string
        self.listen_port = listen_port
        self.p2p_version = p2p_version


class BasePeer(BaseService):
    # Must be defined in subclasses. All items here must be Protocol classes representing
    # different versions of the same P2P sub-protocol (e.g. ETH, LES, etc).
    supported_sub_protocols: Tuple[Type[ProtocolAPI], ...] = ()
    # FIXME: Must be configurable.
    listen_port = 30303
    # Will be set upon the successful completion of a P2P handshake.
    sub_proto: ProtocolAPI = None
    disconnect_reason: DisconnectReason = None

    _event_bus: EndpointAPI = None

    base_protocol: BaseP2PProtocol

    def __init__(self,
                 connection: ConnectionAPI,
                 context: BasePeerContext,
                 event_bus: EndpointAPI = None,
                 ) -> None:
        super().__init__(token=connection.cancel_token, loop=connection.cancel_token.loop)

        # Peer context object
        self.context = context

        # Connection instance
        self.connection = connection
        self.multiplexer = connection.get_multiplexer()

        self.base_protocol = self.connection.get_base_protocol()

        # TODO: need to remove this property but for now it is here to support
        # backwards compat
        for protocol_class in self.supported_sub_protocols:
            try:
                self.sub_proto = self.multiplexer.get_protocol_by_type(protocol_class)
            except UnknownProtocol:
                pass
            else:
                break
        else:
            raise ValidationError("No supported subprotocols found in multiplexer")

        # The self-identifying string that the remote names itself.
        self.client_version_string = self.connection.safe_client_version_string

        # Optional event bus handle
        self._event_bus = event_bus

        # Flag indicating whether the connection this peer represents was
        # established from a dial-out or dial-in (True: dial-in, False:
        # dial-out)
        # TODO: rename to `dial_in` and have a computed property for `dial_out`
        self.inbound = connection.is_dial_in
        self._subscribers: List[PeerSubscriber] = []

        # A counter of the number of messages this peer has received for each
        # message type.
        self.received_msgs: Dict[CommandAPI, int] = collections.defaultdict(int)

        # Manages the boot process
        self.boot_manager = self.get_boot_manager()
        self.connection_tracker = self.setup_connection_tracker()

        self.process_handshake_receipts(
            connection.get_p2p_receipt(),
            connection.protocol_receipts,
        )

    def process_handshake_receipts(self,
                                   devp2p_receipt: DevP2PReceipt,
                                   protocol_receipts: Sequence[HandshakeReceiptAPI]) -> None:
        """
        Noop implementation for subclasses to override.
        """
        pass

    @property
    def has_event_bus(self) -> bool:
        return self._event_bus is not None

    def get_event_bus(self) -> EndpointAPI:
        if self._event_bus is None:
            raise AttributeError(f"No event bus configured for peer {self}")
        return self._event_bus

    def setup_connection_tracker(self) -> BaseConnectionTracker:
        """
        Return an instance of `p2p.tracking.connection.BaseConnectionTracker`
        which will be used to track peer connection failures.
        """
        return NoopConnectionTracker()

    def __str__(self) -> str:
        return f"{self.__class__.__name__} {self.remote}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__} {self.remote!r}"

    #
    # Proxy Transport attributes
    #
    @cached_property
    def remote(self) -> NodeAPI:
        return self.connection.remote

    @property
    def is_closing(self) -> bool:
        return self.multiplexer.is_closing

    def get_extra_stats(self) -> Tuple[str, ...]:
        return tuple()

    @property
    def boot_manager_class(self) -> Type[BasePeerBootManager]:
        return BasePeerBootManager

    def get_boot_manager(self) -> BasePeerBootManager:
        return self.boot_manager_class(self)

    @property
    def received_msgs_count(self) -> int:
        return self.multiplexer.get_total_msg_count()

    def add_subscriber(self, subscriber: 'PeerSubscriber') -> None:
        self._subscribers.append(subscriber)

    def remove_subscriber(self, subscriber: 'PeerSubscriber') -> None:
        if subscriber in self._subscribers:
            self._subscribers.remove(subscriber)

    async def _cleanup(self) -> None:
        self.connection.cancel_nowait()

    def setup_protocol_handlers(self) -> None:
        """
        Hook for subclasses to setup handlers for protocols specific messages.
        """
        pass

    async def _run(self) -> None:
        # setup handler to respond to ping messages
        self.connection.add_command_handler(Ping, self._ping_handler)

        # setup handler for disconnect messages
        self.connection.add_command_handler(Disconnect, self._disconnect_handler)

        # setup handler for protocol messages to pass messages to subscribers
        for protocol in self.multiplexer.get_protocols():
            self.connection.add_protocol_handler(type(protocol), self._handle_subscriber_message)

        self.setup_protocol_handlers()

        # The `boot` process is run in the background to allow the `run` loop
        # to continue so that all of the Peer APIs can be used within the
        # `boot` task.
        self.run_child_service(self.boot_manager)

        # Trigger the connection to start feeding messages though the handlers
        self.connection.start_protocol_streams()

        await self.cancellation()

    async def _ping_handler(self, connection: ConnectionAPI, msg: Payload) -> None:
        self.base_protocol.send_pong()

    async def _disconnect_handler(self, connection: ConnectionAPI, msg: Payload) -> None:
        msg = cast(Dict[str, Any], msg)
        try:
            reason = DisconnectReason(msg['reason'])
        except TypeError:
            self.logger.info('Unrecognized reason: %s', msg['reason_name'])
        else:
            self.disconnect_reason = reason

        self.cancel_nowait()

    async def _handle_subscriber_message(self,
                                         connection: ConnectionAPI,
                                         cmd: CommandAPI,
                                         msg: Payload) -> None:
        subscriber_msg = PeerMessage(self, cmd, msg)
        for subscriber in self._subscribers:
            subscriber.add_msg(subscriber_msg)

    def _disconnect(self, reason: DisconnectReason) -> None:
        if reason is DisconnectReason.bad_protocol:
            self.connection_tracker.record_blacklist(
                self.remote,
                timeout_seconds=BLACKLIST_SECONDS_BAD_PROTOCOL,
                reason="Bad protocol",
            )

        self.logger.debug("Disconnecting from remote peer %s; reason: %s", self.remote, reason.name)
        self.base_protocol.send_disconnect(reason)
        self.cancel_nowait()

    async def disconnect(self, reason: DisconnectReason) -> None:
        """Send a disconnect msg to the remote node and stop this Peer.

        Also awaits for self.cancel() to ensure any pending tasks are cleaned up.

        :param reason: An item from the DisconnectReason enum.
        """
        self._disconnect(reason)
        if self.is_operational:
            await self.cancel()

    def disconnect_nowait(self, reason: DisconnectReason) -> None:
        """
        Non-coroutine version of `disconnect`
        """
        self._disconnect(reason)
        if self.is_operational:
            self.cancel_nowait()


class PeerMessage(NamedTuple):
    peer: BasePeer
    command: CommandAPI
    payload: Payload


class PeerSubscriber(ABC):
    """
    Use the :class:`~p2p.peer.PeerSubscriber` class to subscribe to messages from all or specific
    peers.
    """
    _msg_queue: 'asyncio.Queue[PeerMessage]' = None

    @property
    @abstractmethod
    def subscription_msg_types(self) -> FrozenSet[Type[CommandAPI]]:
        """
        The :class:`p2p.protocol.Command` types that this class subscribes to. Any
        command which is not in this set will not be passed to this subscriber.

        The base command class :class:`p2p.protocol.Command` can be used to enable
        **all** command types.

        .. note: This API only applies to sub-protocol commands. Base protocol
        commands are handled exclusively at the peer level and cannot be
        consumed with this API.
        """
        ...

    @functools.lru_cache(maxsize=64)
    def is_subscription_command(self, cmd_type: Type[CommandAPI]) -> bool:
        return bool(self.subscription_msg_types.intersection(
            {cmd_type, Command}
        ))

    @property
    @abstractmethod
    def msg_queue_maxsize(self) -> int:
        """
        The max size of messages the underlying :meth:`msg_queue` can keep before it starts
        discarding new messages. Implementers need to overwrite this to specify the maximum size.
        """
        ...

    def register_peer(self, peer: BasePeer) -> None:
        """
        Notify about each registered peer in the :class:`~p2p.peer_pool.BasePeerPool`. Is called
        upon subscription for each :class:`~p2p.peer.BasePeer` that exists in the pool at that time
        and then for each :class:`~p2p.peer.BasePeer` that joins the pool later on.

        A :class:`~p2p.peer.PeerSubscriber` that wants to act upon peer registration needs to
        overwrite this method to provide an implementation.
        """
        pass

    def deregister_peer(self, peer: BasePeer) -> None:
        """
        Notify about each :class:`~p2p.peer.BasePeer` that is removed from the
        :class:`~p2p.peer_pool.BasePeerPool`.

        A :class:`~p2p.peer.PeerSubscriber` that wants to act upon peer deregistration needs to
        overwrite this method to provide an implementation.
        """
        pass

    @property
    def msg_queue(self) -> 'asyncio.Queue[PeerMessage]':
        """
        Return the ``asyncio.Queue[PeerMessage]`` that this subscriber uses to receive messages.
        """
        if self._msg_queue is None:
            self._msg_queue = asyncio.Queue(maxsize=self.msg_queue_maxsize)
        return self._msg_queue

    @property
    def queue_size(self) -> int:
        """
        Return the size of the :meth:`msg_queue`.
        """
        return self.msg_queue.qsize()

    def add_msg(self, msg: PeerMessage) -> bool:
        """
        Add a :class:`~p2p.peer.PeerMessage` to the subscriber.
        """
        peer, cmd, _ = msg

        if not self.is_subscription_command(type(cmd)):
            if hasattr(self, 'logger'):
                self.logger.debug2(  # type: ignore
                    "Discarding %s msg from %s; not subscribed to msg type; "
                    "subscriptions: %s",
                    cmd, peer, self.subscription_msg_types,
                )
            return False

        try:
            if hasattr(self, 'logger'):
                self.logger.debug2(  # type: ignore
                    "Adding %s msg from %s to queue; queue_size=%d", cmd, peer, self.queue_size)
            self.msg_queue.put_nowait(msg)
            return True
        except asyncio.queues.QueueFull:
            if hasattr(self, 'logger'):
                self.logger.warning(  # type: ignore
                    "%s msg queue is full; discarding %s msg from %s",
                    self.__class__.__name__, cmd, peer)
            return False

    @contextlib.contextmanager
    def subscribe(self, peer_pool: 'BasePeerPool') -> Iterator[None]:
        """
        Subscribe to all messages of the given :class:`~p2p.peer_pool.BasePeerPool`.
        Implementors need to call this API to start receiving messages from the pool.

        ::
            async def _run(self) -> None:
                with self.subscribe(self._peer_pool):
                    await self.cancellation()

        Once subscribed, messages can be consumed from the :meth:`msg_queue`.
        """

        peer_pool.subscribe(self)
        try:
            yield
        finally:
            peer_pool.unsubscribe(self)

    @contextlib.contextmanager
    def subscribe_peer(self, peer: BasePeer) -> Iterator[None]:
        """
        Subscribe to all messages of the given :class:`~p2p.peer.BasePeer`.
        Implementors need to call this API to start receiving messages from the peer.

        This API is similar to the :meth:`msg_queue` except that it only subscribes to the messages
        of a single peer.

        Once subscribed, messages can be consumed from the :meth:`msg_queue`.
        """
        peer.add_subscriber(self)
        try:
            yield
        finally:
            peer.remove_subscriber(self)


class MsgBuffer(PeerSubscriber):
    logger = logging.getLogger('p2p.peer.MsgBuffer')
    msg_queue_maxsize = 500
    subscription_msg_types = frozenset({Command})

    @to_tuple
    def get_messages(self) -> Iterator[PeerMessage]:
        while not self.msg_queue.empty():
            yield self.msg_queue.get_nowait()


class BasePeerFactory(ABC):
    @property
    @abstractmethod
    def peer_class(self) -> Type[BasePeer]:
        ...

    def __init__(self,
                 privkey: datatypes.PrivateKey,
                 context: BasePeerContext,
                 token: CancelToken,
                 event_bus: EndpointAPI = None) -> None:
        self.privkey = privkey
        self.context = context
        self.cancel_token = token
        self.event_bus = event_bus

    @abstractmethod
    async def get_handshakers(self) -> Tuple[Handshaker, ...]:
        ...

    async def handshake(self, remote: NodeAPI) -> BasePeer:
        p2p_handshake_params = DevP2PHandshakeParams(
            self.context.client_version_string,
            self.context.listen_port,
            self.context.p2p_version,
        )
        handshakers = await self.get_handshakers()
        connection = await handshake(
            remote=remote,
            private_key=self.privkey,
            p2p_handshake_params=p2p_handshake_params,
            protocol_handshakers=handshakers,
            token=self.cancel_token
        )
        return self.create_peer(connection)

    def create_peer(self,
                    connection: ConnectionAPI) -> BasePeer:
        return self.peer_class(
            connection=connection,
            context=self.context,
            event_bus=self.event_bus,
        )
