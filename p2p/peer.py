from abc import ABC, abstractmethod
import asyncio
import collections
import contextlib
import functools
from typing import (
    Any,
    Dict,
    Iterator,
    List,
    NamedTuple,
    FrozenSet,
    Tuple,
    Type,
    TYPE_CHECKING,
)

from async_exit_stack import AsyncExitStack

from lahja import EndpointAPI

from cached_property import cached_property

from eth_utils import (
    get_extended_debug_logger,
    to_tuple,
    ValidationError,
)

from eth_keys import datatypes

from cancel_token import CancelToken

from p2p.abc import (
    BehaviorAPI,
    CommandAPI,
    ConnectionAPI,
    HandshakerAPI,
    NodeAPI,
    ProtocolAPI,
    SessionAPI,
)
from p2p.commands import BaseCommand
from p2p.constants import BLACKLIST_SECONDS_BAD_PROTOCOL
from p2p.disconnect import DisconnectReason
from p2p.exceptions import (
    PeerConnectionLost,
    UnknownProtocol,
)
from p2p.handshake import (
    dial_out,
    DevP2PHandshakeParams,
)
from p2p.service import BaseService
from p2p.p2p_api import P2PAPI
from p2p.p2p_proto import BaseP2PProtocol
from p2p.tracking.connection import (
    BaseConnectionTracker,
    NoopConnectionTracker,
)

if TYPE_CHECKING:
    from p2p.peer_pool import BasePeerPool  # noqa: F401


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

    _event_bus: EndpointAPI = None

    base_protocol: BaseP2PProtocol
    p2p_api: P2PAPI

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

        # TODO: need to remove this property but for now it is here to support
        # backwards compat
        for protocol_class in self.supported_sub_protocols:
            try:
                self.sub_proto = self.connection.get_protocol_by_type(protocol_class)
            except UnknownProtocol:
                pass
            else:
                break
        else:
            raise ValidationError("No supported subprotocols found in Connection")

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
        self.received_msgs: Dict[CommandAPI[Any], int] = collections.defaultdict(int)

        # Manages the boot process
        self.boot_manager = self.get_boot_manager()
        self.connection_tracker = self.setup_connection_tracker()

        self.process_handshake_receipts()
        # This API provides an awaitable so that users of the
        # `peer.connection.get_logic` APIs can wait until the logic APIs have
        # been installed to the connection.
        self.ready = asyncio.Event()

    def process_handshake_receipts(self) -> None:
        """
        Noop implementation for subclasses to override.
        """
        pass

    def get_behaviors(self) -> Tuple[BehaviorAPI, ...]:
        return ()

    @cached_property
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
        return f"{self.__class__.__name__} {self.session}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__} {self.session!r}"

    #
    # Proxy Transport attributes
    #
    @cached_property
    def remote(self) -> NodeAPI:
        return self.connection.remote

    @cached_property
    def session(self) -> SessionAPI:
        return self.connection.session

    @property
    def is_closing(self) -> bool:
        return self.connection.is_closing

    def get_extra_stats(self) -> Tuple[str, ...]:
        return tuple()

    boot_manager_class: Type[BasePeerBootManager] = BasePeerBootManager

    def get_boot_manager(self) -> BasePeerBootManager:
        return self.boot_manager_class(self)

    @property
    def received_msgs_count(self) -> int:
        return self.connection.get_multiplexer().get_total_msg_count()

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
        async with AsyncExitStack() as stack:
            await stack.enter_async_context(P2PAPI().as_behavior().apply(self.connection))
            self.p2p_api = self.connection.get_logic('p2p', P2PAPI)

            for behavior in self.get_behaviors():
                if behavior.should_apply_to(self.connection):
                    await stack.enter_async_context(behavior.apply(self.connection))

            # setup handler for protocol messages to pass messages to subscribers
            for protocol in self.connection.get_protocols():
                self.connection.add_protocol_handler(
                    type(protocol),
                    self._handle_subscriber_message,
                )

            self.setup_protocol_handlers()

            # The `boot` process is run in the background to allow the `run` loop
            # to continue so that all of the Peer APIs can be used within the
            # `boot` task.
            self.run_child_service(self.boot_manager)

            # Trigger the connection to start feeding messages though the handlers
            self.connection.start_protocol_streams()
            self.ready.set()

            await self.cancellation()

    async def _handle_subscriber_message(self,
                                         connection: ConnectionAPI,
                                         cmd: CommandAPI[Any]) -> None:
        subscriber_msg = PeerMessage(self, cmd)
        for subscriber in self._subscribers:
            subscriber.add_msg(subscriber_msg)

    async def disconnect(self, reason: DisconnectReason) -> None:
        """
        On completion of this method, the peer will be disconnected
        and not in the peer pool anymore.
        """
        if reason is DisconnectReason.BAD_PROTOCOL:
            self.connection_tracker.record_blacklist(
                self.remote,
                timeout_seconds=BLACKLIST_SECONDS_BAD_PROTOCOL,
                reason="Bad protocol",
            )
        if hasattr(self, "p2p_api"):
            try:
                await self.p2p_api.disconnect(reason)
            except PeerConnectionLost:
                self.logger.debug("Tried to disconnect from %s, but already disconnected", self)

        if self.is_operational:
            await self.cancel()

        await self.events.finished.wait()

    def disconnect_nowait(self, reason: DisconnectReason) -> None:
        if reason is DisconnectReason.BAD_PROTOCOL:
            self.connection_tracker.record_blacklist(
                self.remote,
                timeout_seconds=BLACKLIST_SECONDS_BAD_PROTOCOL,
                reason="Bad protocol",
            )
        try:
            self.p2p_api.disconnect_nowait(reason)
        except PeerConnectionLost:
            self.logger.debug("Tried to nowait disconnect from %s, but already disconnected", self)


class PeerMessage(NamedTuple):
    peer: BasePeer
    command: CommandAPI[Any]


class PeerSubscriber(ABC):
    """
    Use the :class:`~p2p.peer.PeerSubscriber` class to subscribe to messages from all or specific
    peers.
    """
    _msg_queue: 'asyncio.Queue[PeerMessage]' = None

    @property
    @abstractmethod
    def subscription_msg_types(self) -> FrozenSet[Type[CommandAPI[Any]]]:
        """
        The :class:`p2p.protocol.Command` types that this class subscribes to. Any
        command which is not in this set will not be passed to this subscriber.

        The base command class :class:`p2p.commands.BaseCommand` can be used to enable
        **all** command types.

        .. note: This API only applies to sub-protocol commands. Base protocol
        commands are handled exclusively at the peer level and cannot be
        consumed with this API.
        """
        ...

    @functools.lru_cache(maxsize=64)
    def is_subscription_command(self, cmd_type: Type[CommandAPI[Any]]) -> bool:
        return bool(self.subscription_msg_types.intersection(
            {cmd_type, BaseCommand}
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

    @cached_property
    def msg_queue(self) -> 'asyncio.Queue[PeerMessage]':
        """
        Return the ``asyncio.Queue[PeerMessage]`` that this subscriber uses to receive messages.
        """
        if self._msg_queue is None:
            self._msg_queue = asyncio.Queue(maxsize=self.msg_queue_maxsize)
        return self._msg_queue

    @cached_property
    def queue_size(self) -> int:
        """
        Return the size of the :meth:`msg_queue`.
        """
        return self.msg_queue.qsize()

    def add_msg(self, msg: PeerMessage) -> bool:
        """
        Add a :class:`~p2p.peer.PeerMessage` to the subscriber.
        """
        peer, cmd = msg

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
    logger = get_extended_debug_logger('p2p.peer.MsgBuffer')
    msg_queue_maxsize = 500
    subscription_msg_types = frozenset({BaseCommand})

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
    async def get_handshakers(self) -> Tuple[HandshakerAPI, ...]:
        ...

    async def handshake(self, remote: NodeAPI) -> BasePeer:
        p2p_handshake_params = DevP2PHandshakeParams(
            self.context.client_version_string,
            self.context.listen_port,
            self.context.p2p_version,
        )
        handshakers = await self.get_handshakers()
        connection = await dial_out(
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
