import asyncio
import collections
import functools
from typing import (
    Any,
    DefaultDict,
    Dict,
    Sequence,
    Set,
    Tuple,
    Type,
    Union,
)

from cached_property import cached_property

from eth_keys import keys

from p2p.abc import (
    CommandAPI,
    ConnectionAPI,
    HandlerFn,
    HandshakeReceiptAPI,
    LogicAPI,
    MultiplexerAPI,
    NodeAPI,
    ProtocolAPI,
    SessionAPI,
    SubscriptionAPI,
    THandshakeReceipt,
    TLogic,
    TProtocol,
)
from p2p.disconnect import DisconnectReason
from p2p.exceptions import (
    DuplicateAPI,
    MalformedMessage,
    PeerConnectionLost,
    ReceiptNotFound,
    UnknownAPI,
    UnknownProtocol,
    UnknownProtocolCommand,
)
from p2p.subscription import Subscription
from p2p.service import BaseService
from p2p.p2p_proto import BaseP2PProtocol, DevP2PReceipt, Disconnect
from p2p.typing import Capabilities


class Connection(ConnectionAPI, BaseService):
    _protocol_handlers: DefaultDict[
        Type[ProtocolAPI],
        Set[HandlerFn]
    ]
    _command_handlers: DefaultDict[
        Type[CommandAPI[Any]],
        Set[HandlerFn]
    ]
    _logics: Dict[str, LogicAPI]

    def __init__(self,
                 multiplexer: MultiplexerAPI,
                 devp2p_receipt: DevP2PReceipt,
                 protocol_receipts: Sequence[HandshakeReceiptAPI],
                 is_dial_out: bool) -> None:
        super().__init__(token=multiplexer.cancel_token, loop=multiplexer.cancel_token.loop)
        self._multiplexer = multiplexer
        self._devp2p_receipt = devp2p_receipt
        self.protocol_receipts = tuple(protocol_receipts)
        self.is_dial_out = is_dial_out

        self._protocol_handlers = collections.defaultdict(set)
        self._command_handlers = collections.defaultdict(set)

        # An event that controls when the connection will start reading from
        # the individual multiplexed protocol streams and feeding handlers.
        # This ensures that the connection does not start consuming messages
        # before all necessary handlers have been added
        self._handlers_ready = asyncio.Event()

        self._logics = {}

    def start_protocol_streams(self) -> None:
        self._handlers_ready.set()

    #
    # Primary properties of the connection
    #
    @cached_property
    def is_dial_in(self) -> bool:
        return not self.is_dial_out

    @cached_property
    def remote(self) -> NodeAPI:
        return self._multiplexer.remote

    @cached_property
    def session(self) -> SessionAPI:
        return self._multiplexer.session

    @property
    def is_closing(self) -> bool:
        return self._multiplexer.is_closing

    async def _run(self) -> None:
        try:
            async with self._multiplexer.multiplex():
                for protocol in self._multiplexer.get_protocols():
                    self.run_daemon_task(self._feed_protocol_handlers(protocol))

                await self.cancellation()
        except (PeerConnectionLost, asyncio.CancelledError):
            pass
        except (MalformedMessage,) as err:
            self.logger.debug(
                "Disconnecting peer %s for sending MalformedMessage: %s",
                self.remote,
                err,
            )
            self.get_base_protocol().send(Disconnect(DisconnectReason.BAD_PROTOCOL))
            pass

    async def _cleanup(self) -> None:
        self._multiplexer.close()

    #
    # Subscriptions/Handler API
    #
    async def _feed_protocol_handlers(self, protocol: ProtocolAPI) -> None:
        # do not start consuming from the protocol stream until
        # `start_protocol_streams` has been called and the multiplexer is
        # active.
        try:
            await asyncio.wait_for(asyncio.gather(self._handlers_ready.wait()), timeout=10)
        except asyncio.TimeoutError as err:
            self.logger.info('Timedout waiting for handler ready signal')
            raise asyncio.TimeoutError(
                "The handlers ready event was never set.  Ensure that "
                "`Connection.start_protocol_streams()` is being called"
            ) from err

        # we don't need to use wait_iter here because the multiplexer does it
        # for us.
        async for cmd in self._multiplexer.stream_protocol_messages(protocol):
            self.logger.debug2('Handling command: %s', type(cmd))
            # local copy to prevent multation while iterating
            protocol_handlers = set(self._protocol_handlers[type(protocol)])
            for proto_handler_fn in protocol_handlers:
                self.logger.debug2(
                    'Running protocol handler %s for protocol=%s command=%s',
                    proto_handler_fn,
                    protocol,
                    type(cmd),
                )
                self.run_task(proto_handler_fn(self, cmd))
            command_handlers = set(self._command_handlers[type(cmd)])
            for cmd_handler_fn in command_handlers:
                self.logger.debug2(
                    'Running command handler %s for protocol=%s command=%s',
                    cmd_handler_fn,
                    protocol,
                    type(cmd),
                )
                self.run_task(cmd_handler_fn(self, cmd))

    def add_protocol_handler(self,
                             protocol_class: Type[ProtocolAPI],
                             handler_fn: HandlerFn,
                             ) -> SubscriptionAPI:
        if not self._multiplexer.has_protocol(protocol_class):
            raise UnknownProtocol(
                f"Protocol {protocol_class} was not found int he connected "
                f"protocols: {self._multiplexer.get_protocols()}"
            )
        self._protocol_handlers[protocol_class].add(handler_fn)
        cancel_fn = functools.partial(
            self._protocol_handlers[protocol_class].remove,
            handler_fn,
        )
        return Subscription(cancel_fn)

    def add_command_handler(self,
                            command_type: Type[CommandAPI[Any]],
                            handler_fn: HandlerFn,
                            ) -> SubscriptionAPI:
        for protocol in self._multiplexer.get_protocols():
            if protocol.supports_command(command_type):
                self._command_handlers[command_type].add(handler_fn)
                cancel_fn = functools.partial(
                    self._command_handlers[command_type].remove,
                    handler_fn,
                )
                return Subscription(cancel_fn)
        else:
            raise UnknownProtocolCommand(
                f"Command {command_type} was not found in the connected "
                f"protocols: {self._multiplexer.get_protocols()}"
            )

    #
    # API extension
    #
    def add_logic(self, name: str, logic: LogicAPI) -> SubscriptionAPI:
        if name in self._logics:
            raise DuplicateAPI(
                f"There is already an API registered under the name '{name}': "
                f"{self._logics[name]}"
            )
        self._logics[name] = logic
        cancel_fn = functools.partial(self.remove_logic, name)
        return Subscription(cancel_fn)

    def remove_logic(self, name: str) -> None:
        self._logics.pop(name)

    def has_logic(self, name: str) -> bool:
        return name in self._logics

    def get_logic(self, name: str, logic_type: Type[TLogic]) -> TLogic:
        if not self.has_logic(name):
            raise UnknownAPI(f"No API registered for the name '{name}'")
        logic = self._logics[name]
        if isinstance(logic, logic_type):
            return logic
        else:
            raise TypeError(
                f"Wrong logic type.  expected: {logic_type}  got: {type(logic)}"
            )

    #
    # Access to underlying Multiplexer
    #
    def get_multiplexer(self) -> MultiplexerAPI:
        return self._multiplexer

    #
    # Base Protocol shortcuts
    #
    def get_base_protocol(self) -> BaseP2PProtocol:
        return self._multiplexer.get_base_protocol()

    def get_p2p_receipt(self) -> DevP2PReceipt:
        return self._devp2p_receipt

    #
    # Protocol APIS
    #
    def has_protocol(self, protocol_identifier: Union[ProtocolAPI, Type[ProtocolAPI]]) -> bool:
        return self._multiplexer.has_protocol(protocol_identifier)

    def get_protocols(self) -> Tuple[ProtocolAPI, ...]:
        return self._multiplexer.get_protocols()

    def get_protocol_by_type(self, protocol_type: Type[TProtocol]) -> TProtocol:
        return self._multiplexer.get_protocol_by_type(protocol_type)

    def get_protocol_for_command_type(self, command_type: Type[CommandAPI[Any]]) -> ProtocolAPI:
        return self._multiplexer.get_protocol_for_command_type(command_type)

    def get_receipt_by_type(self, receipt_type: Type[THandshakeReceipt]) -> THandshakeReceipt:
        for receipt in self.protocol_receipts:
            if isinstance(receipt, receipt_type):
                return receipt
        else:
            raise ReceiptNotFound(f"Receipt not found: {receipt_type}")

    #
    # Connection Metadata
    #
    @cached_property
    def remote_capabilities(self) -> Capabilities:
        return self._devp2p_receipt.capabilities

    @cached_property
    def remote_p2p_version(self) -> int:
        return self._devp2p_receipt.version

    @cached_property
    def negotiated_p2p_version(self) -> int:
        return self.get_base_protocol().version

    @cached_property
    def remote_public_key(self) -> keys.PublicKey:
        return keys.PublicKey(self._devp2p_receipt.remote_public_key)

    @cached_property
    def client_version_string(self) -> str:
        return self._devp2p_receipt.client_version_string

    @cached_property
    def safe_client_version_string(self) -> str:
        # limit number of chars to be displayed, and try to keep printable ones only
        # MAGIC 256: arbitrary, "should be enough for everybody"
        if len(self.client_version_string) <= 256:
            return self.client_version_string

        truncated_client_version_string = self.client_version_string[:253] + '...'
        if truncated_client_version_string.isprintable():
            return truncated_client_version_string
        else:
            return repr(truncated_client_version_string)
