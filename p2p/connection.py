import asyncio
import collections
import functools
from typing import DefaultDict, Sequence, Set, Type

from eth_keys import keys

from p2p.abc import (
    CommandAPI,
    HandlerSubscriptionAPI,
    HandshakeReceiptAPI,
    MultiplexerAPI,
    NodeAPI,
    ProtocolAPI,
    ProtocolHandlerFn,
    CommandHandlerFn,
    ConnectionAPI,
)
from p2p.exceptions import (
    PeerConnectionLost,
    UnknownProtocol,
    UnknownProtocolCommand,
)
from p2p.handshake import DevP2PReceipt
from p2p.handler_subscription import HandlerSubscription
from p2p.service import BaseService
from p2p.p2p_proto import BaseP2PProtocol
from p2p.typing import Capabilities


class Connection(ConnectionAPI, BaseService):
    _protocol_handlers: DefaultDict[
        Type[ProtocolAPI],
        Set[ProtocolHandlerFn]
    ]
    _command_handlers: DefaultDict[
        Type[CommandAPI],
        Set[CommandHandlerFn]
    ]

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

    def start_protocol_streams(self) -> None:
        self._handlers_ready.set()

    #
    # Primary properties of the connection
    #
    @property
    def is_dial_in(self) -> bool:
        return not self.is_dial_out

    @property
    def remote(self) -> NodeAPI:
        return self._multiplexer.remote

    async def _run(self) -> None:
        try:
            async with self._multiplexer.multiplex():
                for protocol in self._multiplexer.get_protocols():
                    self.run_daemon_task(self._feed_protocol_handlers(protocol))

                await self.cancellation()
        except (PeerConnectionLost, asyncio.CancelledError):
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
        async for cmd, msg in self._multiplexer.stream_protocol_messages(protocol):
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
                self.run_task(proto_handler_fn(self, cmd, msg))
            command_handlers = set(self._command_handlers[type(cmd)])
            for cmd_handler_fn in command_handlers:
                self.logger.debug2(
                    'Running command handler %s for protocol=%s command=%s',
                    cmd_handler_fn,
                    protocol,
                    type(cmd),
                )
                self.run_task(cmd_handler_fn(self, msg))

    def add_protocol_handler(self,
                             protocol_class: Type[ProtocolAPI],
                             handler_fn: ProtocolHandlerFn,
                             ) -> HandlerSubscriptionAPI:
        if not self._multiplexer.has_protocol(protocol_class):
            raise UnknownProtocol(
                f"Protocol {protocol_class} was not found int he connected "
                f"protocols: {self._multiplexer.get_protocols()}"
            )
        self._protocol_handlers[protocol_class].add(handler_fn)
        remove_fn = functools.partial(
            self._protocol_handlers[protocol_class].remove,
            handler_fn,
        )
        return HandlerSubscription(remove_fn)

    def add_command_handler(self,
                            command_type: Type[CommandAPI],
                            handler_fn: CommandHandlerFn,
                            ) -> HandlerSubscriptionAPI:
        for protocol in self._multiplexer.get_protocols():
            if protocol.supports_command(command_type):
                self._command_handlers[command_type].add(handler_fn)
                remove_fn = functools.partial(
                    self._command_handlers[command_type].remove,
                    handler_fn,
                )
                return HandlerSubscription(remove_fn)
        else:
            raise UnknownProtocolCommand(
                f"Command {command_type} was not found in the connected "
                f"protocols: {self._multiplexer.get_protocols()}"
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
    # Connection Metadata
    #
    @property
    def remote_capabilities(self) -> Capabilities:
        return self._devp2p_receipt.capabilities

    @property
    def remote_p2p_version(self) -> int:
        return self._devp2p_receipt.version

    @property
    def negotiated_p2p_version(self) -> int:
        return self.get_base_protocol().version

    @property
    def remote_public_key(self) -> keys.PublicKey:
        return keys.PublicKey(self._devp2p_receipt.remote_public_key)

    @property
    def client_version_string(self) -> str:
        return self._devp2p_receipt.client_version_string

    @property
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
