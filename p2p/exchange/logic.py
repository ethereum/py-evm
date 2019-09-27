from typing import Any, AsyncIterator

from async_generator import asynccontextmanager

from p2p.abc import ConnectionAPI, LogicAPI
from p2p.exceptions import UnknownProtocol
from p2p.logic import BaseLogic

from .abc import ExchangeAPI


class ExchangeLogic(BaseLogic):
    """
    A thin wrapper around an exchange which handles running the services and
    checking whether it's applicable to the connection
    """
    exchange: ExchangeAPI[Any, Any, Any]

    def __init__(self, exchange: ExchangeAPI[Any, Any, Any]) -> None:
        self.exchange = exchange

    def qualifier(self, connection: ConnectionAPI, logic: LogicAPI) -> bool:
        try:
            protocol = connection.get_protocol_for_command_type(
                self.exchange.get_request_cmd_type()
            )
        except UnknownProtocol:
            return False
        else:
            return protocol.supports_command(self.exchange.get_response_cmd_type())

    @asynccontextmanager
    async def apply(self, connection: ConnectionAPI) -> AsyncIterator[None]:
        async with self.exchange.run_exchange(connection):
            yield
