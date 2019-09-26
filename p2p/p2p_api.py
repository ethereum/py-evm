import logging
from typing import Optional

from cached_property import cached_property

from p2p.abc import ConnectionAPI
from p2p.logic import Application, CommandHandler
from p2p.disconnect import DisconnectReason
from p2p.p2p_proto import Disconnect, Ping, Pong
from p2p.qualifiers import always


class PongWhenPinged(CommandHandler[Ping]):
    """
    Sends a `Pong` message anytime a `Ping` message is received.
    """
    command_type = Ping

    async def handle(self, connection: ConnectionAPI, cmd: Ping) -> None:
        connection.get_base_protocol().send(Pong(None))


class CancelOnDisconnect(CommandHandler[Disconnect]):
    """
    Listens for `Disconnect` messages, recording the *reason* and triggering
    cancellation of the Connection.
    """
    command_type = Disconnect

    logger = logging.getLogger('p2p.p2p_api.P2PAPI')

    disconnect_reason: DisconnectReason = None

    async def handle(self, connection: ConnectionAPI, cmd: Disconnect) -> None:
        self.disconnect_reason = cmd.payload

        if connection.is_operational:
            connection.cancel_nowait()


class P2PAPI(Application):
    name = 'p2p'
    qualifier = always  # always valid for all connections.

    logger = logging.getLogger('p2p.p2p_api.P2PAPI')

    local_disconnect_reason: DisconnectReason = None

    def __init__(self) -> None:
        self.add_child_behavior(PongWhenPinged().as_behavior())
        self._disconnect_handler = CancelOnDisconnect()
        self.add_child_behavior(self._disconnect_handler.as_behavior())

    #
    # Properties from handshake
    #
    @cached_property
    def safe_client_version_string(self) -> str:
        return self.connection.safe_client_version_string

    @cached_property
    def client_version_string(self) -> str:
        return self.connection.client_version_string

    #
    # Disconnect API
    #
    @property
    def remote_disconnect_reason(self) -> Optional[DisconnectReason]:
        """
        The reason "they" disconnected from "us"
        """
        return self._disconnect_handler.disconnect_reason

    def _disconnect(self, reason: DisconnectReason) -> None:
        self.logger.debug(
            "Sending Disconnect to remote peer %s; reason: %s",
            self.connection,
            reason.name,
        )
        self.send_disconnect(reason)
        self.local_disconnect_reason = reason

    async def disconnect(self, reason: DisconnectReason) -> None:
        self._disconnect(reason)
        if self.connection.is_operational:
            await self.connection.cancel()

    def disconnect_nowait(self, reason: DisconnectReason) -> None:
        self._disconnect(reason)
        if self.connection.is_operational:
            self.connection.cancel_nowait()

    #
    # Sending Pings
    #
    def send_ping(self) -> None:
        self.connection.get_base_protocol().send(Ping(None))

    def send_pong(self) -> None:
        self.connection.get_base_protocol().send(Pong(None))

    def send_disconnect(self, reason: DisconnectReason) -> None:
        self.connection.get_base_protocol().send(Disconnect(reason))
