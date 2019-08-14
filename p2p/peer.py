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

from eth_utils import to_tuple

from eth_keys import datatypes

from cancel_token import CancelToken

from p2p.abc import CommandAPI, MultiplexerAPI, NodeAPI, ProtocolAPI
from p2p.constants import BLACKLIST_SECONDS_BAD_PROTOCOL
from p2p.disconnect import DisconnectReason
from p2p.exceptions import (
    MalformedMessage,
    PeerConnectionLost,
    UnexpectedMessage,
)
from p2p.handshake import (
    negotiate_protocol_handshakes,
    DevP2PHandshakeParams,
    DevP2PReceipt,
    HandshakeReceipt,
    Handshaker,
)
from p2p.service import BaseService
from p2p.p2p_proto import (
    BaseP2PProtocol,
    Disconnect,
    Ping,
    Pong,
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
                    token: CancelToken,
                    ) -> Tuple[MultiplexerAPI, DevP2PReceipt, Tuple[HandshakeReceipt, ...]]:
    """
    Perform the auth and P2P handshakes with the given remote.

    Return a `Multiplexer` object along with the handshake receipts.

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

    return multiplexer, devp2p_receipt, protocol_receipts


async def receive_handshake(reader: asyncio.StreamReader,
                            writer: asyncio.StreamWriter,
                            private_key: datatypes.PrivateKey,
                            p2p_handshake_params: DevP2PHandshakeParams,
                            protocol_handshakers: Tuple[Handshaker, ...],
                            token: CancelToken,
                            ) -> Tuple[MultiplexerAPI, DevP2PReceipt, Tuple[HandshakeReceipt, ...]]:
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

    return multiplexer, devp2p_receipt, protocol_receipts


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
                 multiplexer: MultiplexerAPI,
                 devp2p_receipt: DevP2PReceipt,
                 protocol_receipts: Sequence[HandshakeReceipt],
                 context: BasePeerContext,
                 inbound: bool,
                 event_bus: EndpointAPI = None,
                 ) -> None:
        super().__init__(token=multiplexer.cancel_token, loop=multiplexer.cancel_token.loop)

        # This is currently only used to have access to the `vm_configuration`
        # for ETH/LES peers to do their DAO fork check.
        self.context = context

        # Connection instance
        self.multiplexer = multiplexer

        self.base_protocol = self.multiplexer.get_base_protocol()

        # TODO: need to remove this property but for now it is here to support
        # backwards compat
        self.sub_proto = self.multiplexer.get_protocols()[1]

        # The self-identifying string that the remote names itself.
        self.client_version_string = devp2p_receipt.client_version_string

        # Optional event bus handle
        self._event_bus = event_bus

        # Flag indicating whether the connection this peer represents was
        # established from a dial-out or dial-in (True: dial-in, False:
        # dial-out)
        # TODO: rename to `dial_in` and have a computed property for `dial_out`
        self.inbound = inbound
        self._subscribers: List[PeerSubscriber] = []

        # A counter of the number of messages this peer has received for each
        # message type.
        self.received_msgs: Dict[CommandAPI, int] = collections.defaultdict(int)

        # Manages the boot process
        self.boot_manager = self.get_boot_manager()
        self.connection_tracker = self.setup_connection_tracker()

        self.process_receipts(devp2p_receipt, protocol_receipts)

    def process_receipts(self,
                         devp2p_receipt: DevP2PReceipt,
                         protocol_receipts: Sequence[HandshakeReceipt]) -> None:
        """
        Hook for subclasses to initialize data based on the protocol handshake.
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
        return self.multiplexer.remote

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
        self.multiplexer.close()

    async def _run(self) -> None:
        # The `boot` process is run in the background to allow the `run` loop
        # to continue so that all of the Peer APIs can be used within the
        # `boot` task.
        self.run_child_service(self.boot_manager)
        try:
            async with self.multiplexer.multiplex():
                self.run_daemon_task(self.handle_p2p_proto_stream())
                self.run_daemon_task(self.handle_sub_proto_stream())
                await self.cancellation()
        except PeerConnectionLost as err:
            self.logger.debug('Peer connection lost: %s: %r', self, err)
            self.cancel_nowait()
        except MalformedMessage as err:
            self.logger.debug('MalformedMessage error with peer: %s: %r', self, err)
            await self.disconnect(DisconnectReason.subprotocol_error)
        except TimeoutError as err:
            # TODO: we should send a ping and see if we get back a pong...
            self.logger.debug('TimeoutError error with peer: %s: %r', self, err)
            await self.disconnect(DisconnectReason.timeout)

    async def handle_p2p_proto_stream(self) -> None:
        """Handle the base protocol (P2P) messages."""
        async for cmd, msg in self.multiplexer.stream_protocol_messages(self.base_protocol):
            self.handle_p2p_msg(cmd, msg)

    def handle_p2p_msg(self, cmd: CommandAPI, msg: Payload) -> None:
        """Handle the base protocol (P2P) messages."""
        if isinstance(cmd, Disconnect):
            msg = cast(Dict[str, Any], msg)
            try:
                reason = DisconnectReason(msg['reason'])
            except TypeError:
                self.logger.info('Unrecognized reason: %s', msg['reason'])
            else:
                self.disconnect_reason = reason
            self.cancel_nowait()
            return
        elif isinstance(cmd, Ping):
            self.base_protocol.send_pong()
        elif isinstance(cmd, Pong):
            # Currently we don't do anything when we get a pong, but eventually we should
            # update the last time we heard from a peer in our DB (which doesn't exist yet).
            pass
        else:
            raise UnexpectedMessage(f"Unexpected msg: {cmd} ({msg})")

    async def handle_sub_proto_stream(self) -> None:
        async for cmd, msg in self.multiplexer.stream_protocol_messages(self.sub_proto):
            self.handle_sub_proto_msg(cmd, msg)

    def handle_sub_proto_msg(self, cmd: CommandAPI, msg: Payload) -> None:
        cmd_type = type(cmd)

        if self._subscribers:
            was_added = tuple(
                subscriber.add_msg(PeerMessage(self, cmd, msg))
                for subscriber
                in self._subscribers
            )
            if not any(was_added):
                self.logger.warning(
                    "Peer %s has no subscribers for msg type %s",
                    self,
                    cmd_type.__name__,
                )
        else:
            self.logger.warning("Peer %s has no subscribers, discarding %s msg", self, cmd)

    def _disconnect(self, reason: DisconnectReason) -> None:
        if not isinstance(reason, DisconnectReason):
            raise ValueError(
                f"Reason must be an item of DisconnectReason, got {reason}"
            )

        self.disconnect_reason = reason
        if reason is DisconnectReason.bad_protocol:
            self.connection_tracker.record_blacklist(
                self.remote,
                timeout_seconds=BLACKLIST_SECONDS_BAD_PROTOCOL,
                reason="Bad protocol",
            )

        self.logger.debug("Disconnecting from remote peer %s; reason: %s", self.remote, reason.name)
        self.base_protocol.send_disconnect(reason.value)
        self.multiplexer.close()

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
        multiplexer, devp2p_receipt, protocol_receipts = await handshake(
            remote=remote,
            private_key=self.privkey,
            p2p_handshake_params=p2p_handshake_params,
            protocol_handshakers=handshakers,
            token=self.cancel_token
        )
        return self.create_peer(
            multiplexer=multiplexer,
            devp2p_receipt=devp2p_receipt,
            protocol_receipts=protocol_receipts,
            inbound=False,
        )

    def create_peer(self,
                    multiplexer: MultiplexerAPI,
                    devp2p_receipt: DevP2PReceipt,
                    protocol_receipts: Sequence[HandshakeReceipt],
                    inbound: bool) -> BasePeer:
        return self.peer_class(
            multiplexer=multiplexer,
            devp2p_receipt=devp2p_receipt,
            protocol_receipts=protocol_receipts,
            context=self.context,
            inbound=False,
            event_bus=self.event_bus,
        )
